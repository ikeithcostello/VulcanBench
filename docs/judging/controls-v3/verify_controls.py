"""Every control must produce identical behaviour; only maintainability differs.

Run: python docs/judging/controls-v3/verify_controls.py
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAMPLE = """# opening balances
2026-09-01,alpha,card,1000
2026-09-01,beta,bank,500

2026-09-02,alpha,cash,-1200
2026-09-02,gamma,card,10
"""
EXPECTED = {"alpha": 1000 - 59 - 1200, "beta": 475, "gamma": 10 - 30}


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    failures = []
    for path in sorted(HERE.glob("control-*.py")):
        m = load(path)
        totals = m.balances(m.parse_records(SAMPLE))
        lines = m.render(totals)
        checks = [
            totals == EXPECTED,
            lines[0] == "alpha  (2.59)",
            lines[1] == "beta  4.75",
            lines[2] == "gamma  (0.20)",
        ]
        try:
            m.parse_records("2026-09-01,alpha,card")
            checks.append(False)
        except ValueError:
            checks.append(True)
        try:
            m.balances([("x", "crypto", 5)])
            checks.append(False)
        except ValueError:
            checks.append(True)
        if not all(checks):
            failures.append((path.name, checks, totals, lines))
    quirk = load(HERE / "control-7-legacy-quirk.py")
    ordered = quirk.render({"_suspense": 100, "alpha": 1, "zeta": 2})
    if ordered[-1] != "_suspense  1.00":
        failures.append(("control-7 quirk", ordered))
    for failure in failures:
        print("FAIL", *failure)
    print("ok" if not failures else f"{len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
