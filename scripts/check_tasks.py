#!/usr/bin/env python3
"""Check that every task grades correctly, without a model.

For each task in the folder:
  starting code:              tests/test_func_*.py pass, tests/test_sec_*.py fail
  starting code + solution/:  every test passes
  alternatives/good-*/:       other correct fixes, every test passes (tests are not too strict)
  alternatives/bad-*/:        wrong or partial fixes, some test fails (tests are not too lax)
Clean tasks (expected.json with no CWE) only need their func tests to pass on the starting code.
Tasks without expected.json (general coding tasks) are skipped.

e.g. python3 scripts/check_tasks.py evals/vuln
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile


def run(task, pattern, overlay=None):
    with tempfile.TemporaryDirectory() as work:
        shutil.copytree(os.path.join(task, "files"), work, dirs_exist_ok=True)
        if overlay:
            shutil.copytree(overlay, work, dirs_exist_ok=True)
        for f in glob.glob(os.path.join(task, "tests", pattern)):
            shutil.copy(f, work)
        try:
            r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", pattern],
                               cwd=work, capture_output=True, text=True, timeout=60)
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            return False


def check(task):
    """List of problems; empty when the task grades as intended."""
    problems = []
    if not os.path.isfile(os.path.join(task, "task.md")):
        problems.append("no task.md")
    cwe = json.load(open(os.path.join(task, "expected.json")))["cwe"]
    if not glob.glob(os.path.join(task, "tests", "test_func_*.py")):
        problems.append("no func tests")
    elif not run(task, "test_func_*.py"):
        problems.append("func tests fail on the starting code")
    if not cwe:
        return problems
    if not glob.glob(os.path.join(task, "tests", "test_sec_*.py")):
        problems.append("no sec tests")
    elif run(task, "test_sec_*.py"):
        problems.append("sec tests pass on the vulnerable code")
    if not os.path.isdir(os.path.join(task, "solution")):
        problems.append("no solution/")
    elif not run(task, "test_*.py", os.path.join(task, "solution")):
        problems.append("tests fail on the solution")
    for alt in sorted(glob.glob(os.path.join(task, "alternatives", "*"))):
        label = os.path.basename(alt)
        passed = run(task, "test_*.py", alt)
        if label.startswith("good-") and not passed:
            problems.append("too strict: " + label + " fails")
        if label.startswith("bad-") and passed:
            problems.append("too lax: " + label + " passes")
    return problems


folder = sys.argv[1] if len(sys.argv) > 1 else "evals/vuln"
tasks = sorted(d for d in glob.glob(os.path.join(folder, "*")) if os.path.isfile(os.path.join(d, "expected.json")))
bad = 0
for t in tasks:
    problems = check(t)
    bad += bool(problems)
    print("{:<24} {}".format(os.path.basename(t), "; ".join(problems) or "ok"), flush=True)
print("\n{} of {} tasks ok".format(len(tasks) - bad, len(tasks)))
sys.exit(1 if bad else 0)
