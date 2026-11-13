#!/usr/bin/env python3
"""Check that every task grades correctly, without a model.

Security tasks (expected.json):
  starting code:              tests/test_func_*.py pass, tests/test_sec_*.py fail
  starting code + solution/:  every test passes
  Clean tasks (no CWE in expected.json) only need their func tests to pass on the starting code.
Coding tasks with a solution/ (e.g. evals/long):
  starting code:              some test fails
  starting code + solution/:  every test passes, and unittest runs as many tests as eval.py counts
Both kinds:
  alternatives/good-*/:       other correct fixes, every test passes (tests are not too strict)
  alternatives/bad-*/:        wrong or partial fixes, some test fails (tests are not too lax)
Tasks with neither expected.json nor solution/ (the sample coding tasks) are skipped.

e.g. python3 scripts/check_tasks.py evals/vuln evals/long
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


def run(task, pattern, overlay=None):
    """(all passed, unittest output)"""
    with tempfile.TemporaryDirectory() as work:
        shutil.copytree(os.path.join(task, "files"), work, dirs_exist_ok=True)
        if overlay:
            shutil.copytree(overlay, work, dirs_exist_ok=True)
        for f in glob.glob(os.path.join(task, "tests", pattern)):
            shutil.copy(f, work)
        try:
            r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", pattern],
                               cwd=work, capture_output=True, text=True, timeout=60)
            return r.returncode == 0, r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            return False, "timed out"


def defined_tests(task):
    """Same count as eval.py uses for the score."""
    return sum(len(re.findall(r"^\s+def test_", open(f).read(), re.M))
               for f in glob.glob(os.path.join(task, "tests", "test_*.py")))


def check_security(task, problems):
    """False when the task has nothing more to check (clean task)."""
    cwe = json.load(open(os.path.join(task, "expected.json")))["cwe"]
    if not glob.glob(os.path.join(task, "tests", "test_func_*.py")):
        problems.append("no func tests")
    elif not run(task, "test_func_*.py")[0]:
        problems.append("func tests fail on the starting code")
    if not cwe:
        return False
    if not glob.glob(os.path.join(task, "tests", "test_sec_*.py")):
        problems.append("no sec tests")
    elif run(task, "test_sec_*.py")[0]:
        problems.append("sec tests pass on the vulnerable code")
    return True


def check(task):
    """List of problems; empty when the task grades as intended."""
    problems = []
    if not os.path.isfile(os.path.join(task, "task.md")):
        problems.append("no task.md")
    if os.path.isfile(os.path.join(task, "expected.json")):
        if not check_security(task, problems):
            return problems
    elif run(task, "test_*.py")[0]:
        problems.append("tests pass on the starting code")
    solution = os.path.join(task, "solution")
    if not os.path.isdir(solution):
        problems.append("no solution/")
    else:
        ok, out = run(task, "test_*.py", solution)
        if not ok:
            problems.append("tests fail on the solution")
        ran = re.search(r"Ran (\d+) test", out)
        if not ran or int(ran.group(1)) != defined_tests(task):
            problems.append("unittest ran {} tests, eval.py counts {}".format(
                ran.group(1) if ran else 0, defined_tests(task)))
    for alt in sorted(glob.glob(os.path.join(task, "alternatives", "*"))):
        label = os.path.basename(alt)
        passed = run(task, "test_*.py", alt)[0]
        if label.startswith("good-") and not passed:
            problems.append("too strict: " + label + " fails")
        if label.startswith("bad-") and passed:
            problems.append("too lax: " + label + " passes")
    return problems


def graded(d):
    return os.path.isfile(os.path.join(d, "expected.json")) or os.path.isdir(os.path.join(d, "solution"))


folders = sys.argv[1:] or ["evals/vuln"]
tasks = sorted(d for f in folders for d in glob.glob(os.path.join(f, "*")) if graded(d))
bad = 0
for t in tasks:
    problems = check(t)
    bad += bool(problems)
    print("{:<24} {}".format(os.path.basename(t), "; ".join(problems) or "ok"), flush=True)
print("\n{} of {} tasks ok".format(len(tasks) - bad, len(tasks)))
sys.exit(1 if bad else 0)
