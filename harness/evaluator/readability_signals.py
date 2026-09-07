"""Deterministic human-readability signals for Python sources.

These are unscored diagnostics for the code-quality-maintenance-v3 protocol.
They measure things a human reader pays for that a model reader does not:
statements packed onto one line, names that carry no meaning, unexplained
numeric literals, deep nesting, long functions, and hidden module state.
Every signal is gameable in isolation, so none enters the composite. They are
reported next to the reviewed score and used in calibration to check that the
panel's presentation dimension moves in the expected direction.

CLI: python -m harness.evaluator.readability_signals FILE [FILE ...]
"""

from __future__ import annotations

import ast
import io
import json
import statistics
import sys
import tokenize
from pathlib import Path

_UNREMARKABLE_LITERALS = {0, 1, 2, -1}


def analyze_source(source: str) -> dict:
    """Signals for one Python module. Raises SyntaxError on unparsable input."""
    tree = ast.parse(source)
    statements = [node for node in ast.walk(tree) if isinstance(node, ast.stmt)]
    stmt_lines = [node.lineno for node in statements]
    per_line = {}
    for line in stmt_lines:
        per_line[line] = per_line.get(line, 0) + 1
    code_line_count = len(per_line) or 1

    bound = _bound_names(tree)
    lengths = [len(name) for name in bound]
    short = [name for name in bound if len(name) <= 2 and name != "_"]

    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    function_lengths = [n.end_lineno - n.lineno + 1 for n in functions if n.end_lineno]

    comment_lines = 0
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            comment_lines += 1
    docstrings = sum(1 for n in [tree, *functions, *[c for c in ast.walk(tree) if isinstance(c, ast.ClassDef)]]
                     if ast.get_docstring(n))

    return {
        "code_lines": code_line_count,
        "statements": len(statements),
        "statements_per_code_line": round(len(statements) / code_line_count, 3),
        "max_statements_on_one_line": max(per_line.values(), default=0),
        "bound_names": len(bound),
        "short_name_fraction": round(len(short) / len(bound), 3) if bound else 0.0,
        "mean_bound_name_length": round(statistics.mean(lengths), 2) if lengths else 0.0,
        "magic_literals": _magic_literal_count(tree),
        "magic_literals_per_100_lines": round(100 * _magic_literal_count(tree) / code_line_count, 2),
        "max_nesting_depth": _max_depth(tree),
        "longest_function_lines": max(function_lengths, default=0),
        "comment_lines": comment_lines,
        "comment_line_fraction": round(comment_lines / code_line_count, 3),
        "docstrings": docstrings,
        "module_mutable_state": _module_mutable_state(tree),
        "max_line_length": max((len(line) for line in source.splitlines()), default=0),
    }


def _bound_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return {n for n in names if not n.startswith("__")}


def _magic_literal_count(tree: ast.AST) -> int:
    """Numeric literals other than 0, 1, 2, -1 that are not bound to an UPPER_CASE name."""
    named: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
            if targets and all(t.id.isupper() or t.id.replace("_", "").isupper() for t in targets):
                named.add(id(node.value))
    count = 0
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
                and node.value not in _UNREMARKABLE_LITERALS and id(node) not in named):
            count += 1
    return count


def _max_depth(tree: ast.AST) -> int:
    nesting = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    def depth(node: ast.AST, current: int) -> int:
        deepest = current
        for child in ast.iter_child_nodes(node):
            step = current + 1 if isinstance(child, nesting) else current
            deepest = max(deepest, depth(child, step))
        return deepest

    return depth(tree, 0)


def _module_mutable_state(tree: ast.Module) -> int:
    """Module-level names bound to list, dict, or set literals that are not UPPER_CASE."""
    count = 0
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp)):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.isupper():
                    count += 1
    return count


def analyze_files(paths: list[Path]) -> dict[str, dict]:
    results = {}
    for path in paths:
        try:
            results[str(path)] = analyze_source(path.read_text())
        except SyntaxError as error:
            results[str(path)] = {"error": f"syntax error: {error.msg} line {error.lineno}"}
    return results


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    print(json.dumps(analyze_files([Path(p) for p in argv]), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
