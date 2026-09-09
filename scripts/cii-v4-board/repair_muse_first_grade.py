"""Regrade the frozen first Muse patch; no model calls, original receipt preserved."""
import copy
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from harness.evaluator.evaluate import evaluate_run
from harness.regrade import _apply_patch, _git
from harness.tasks import load_task, prepare_workspace, task_hash
from harness.verifier import run_declarative_verifier

ROOT = Path(__file__).resolve().parents[2]
os.environ["PATH"] = str(ROOT/".venv/bin") + os.pathsep + os.environ["PATH"]
run = ROOT/"runs-muse13-cii-v4/minimal/legacy-settlecore-binary-parity-81946297"
original = json.loads((run/"summary.json").read_text())
task = load_task(original["task_id"], ROOT/"tasks/coding-intelligence-index-v4")
assert task_hash(task) == original["task_hash"]
patch = (run/"final.patch").read_text()
receipt = {"at": datetime.now(UTC).isoformat(), "task_hash": task_hash(task),
           "patch_sha256": hashlib.sha256(patch.encode()).hexdigest(), "no_model_calls": True,
           "original_summary_sha256": hashlib.sha256((run/"summary.json").read_bytes()).hexdigest()}
scratch = Path(tempfile.mkdtemp(prefix="vb-muse-grading-audit-"))
for label, diff in [("base", ""), ("gold", task.gold_patch.read_text()), ("saved_solution", patch)]:
    ws = scratch/label
    prepare_workspace(task, ws)
    _git(["init", "-q"], ws)
    _git(["add", "-A"], ws)
    _git(["commit", "-q", "--allow-empty", "-m", "base"],ws)
    _apply_patch(ws,diff)
    changed = _git(["diff", "--name-only"],ws).stdout.splitlines()
    if label == "saved_solution":
        bad_env = {**os.environ, "PATH": "/Users/morganlinton/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"}
        p = subprocess.run("PYTHONPATH=. python -m pytest --version", shell=True, cwd=ws,
                           env=bad_env, capture_output=True, text=True, check=False)
        receipt["original_path_probe"] = {"exit":p.returncode,"stdout":p.stdout,"stderr":p.stderr}
    verified = run_declarative_verifier(task,ws)
    receipt[label] = verified
    if label == "saved_solution":
        scored = evaluate_run(functional=verified["scores"]["functional"],
            total_tokens=original["total_tokens"], steps=original["steps"], workspace=ws,
            patch=patch, changed_files=changed, issue=task.issue, verifier_payload=verified,
            judges_enabled=False)
        assert scored["quality"] is not None and scored["security"] is not None
        corrected = copy.deepcopy(original)
        corrected["scores"] = scored
        corrected["verifier"] = verified
        corrected["grading_correction"] = {"receipt": "grading-repair.json",
            "reason": "Restore verifier/analyzer venv PATH; saved patch unchanged",
            "solver_duration_unchanged": True, "no_model_calls": True}
assert receipt["base"]["scores"]["functional"] == 0
assert receipt["base"]["pass_to_pass_ok"]
assert receipt["gold"]["scores"]["functional"] == 1
backup = run/"summary.original-invalid-grading.json"
assert not backup.exists(), "Already repaired; inspect existing receipt"
backup.write_bytes((run/"summary.json").read_bytes())
(run/"grading-repair.json").write_text(json.dumps(receipt,indent=2)+"\n")
(run/"summary.json").write_text(json.dumps(corrected,indent=2)+"\n")
print(json.dumps({"controls": {k:receipt[k]["scores"] for k in ["base","gold","saved_solution"]},
    "corrected_scores":corrected["scores"],"original_path_probe":receipt["original_path_probe"]},indent=2))
