#!/usr/bin/env python3
"""Coding task eval: the running model solves tasks with tools and is graded by tests.

Task folder (<tasks>/<name>/)
  task.md         instructions
  files/          starting code (copied into the model's work folder)
  tests/          test_*.py for grading; recopied before every run so the model cannot change them
  expected.json   security tasks only: {"cwe": ["CWE-89", ...]}, or {"cwe": []} for code with no vulnerability
  solution/       reference fix, used only by scripts/check_tasks.py

Security tasks split their tests. The model's run_tests tool runs only tests/test_func_*.py
(behavior must not change); tests/test_sec_*.py (the attack) runs only at grading. The model
reports what it found in FINDINGS.json, which is graded against expected.json.

Tools the model uses: list_files, read_file, write_file, run_tests
Output: a row per task + one line per model appended to <out>/summary.csv (summary-<set>.csv
for task sets other than evals/tasks)

e.g. ./serve.sh eval
     ./serve.sh eval --tasks evals/vuln
     ./serve.sh eval --tasks evals/vuln --only sql-injection,xss
"""
import argparse
import csv
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

p = argparse.ArgumentParser()
p.add_argument("--tasks", default="evals/tasks", help="task folder")
p.add_argument("--only", default="", help="run only these comma-separated task names")
p.add_argument("--max-turns", type=int, default=15, help="max model calls per task")
p.add_argument("--out", default="results/eval", help="output folder")
args = p.parse_args()

URL = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1")
HEADERS = {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("VLLM_API_KEY", "")}
MODEL = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/models", headers=HEADERS), timeout=10))["data"][0]["id"]

SYSTEM = ("You are a coding agent working in a small repository. Use the tools to inspect files, edit them, "
          "and run the tests. Keep working until the task is done, then reply with a one-line summary.")
TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List files in the repository",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file",
                                      "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Create or overwrite a file with the full content",
                                      "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                                                     "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "run_tests", "description": "Run the test suite and return the output",
                                      "parameters": {"type": "object", "properties": {}}}},
]
ALL_TESTS, FUNC_TESTS, SEC_TESTS = "test_*.py", "test_func_*.py", "test_sec_*.py"


def chat(messages):
    body = {"model": MODEL, "messages": messages, "tools": TOOLS, "max_tokens": 8192}
    req = urllib.request.Request(URL + "/chat/completions", json.dumps(body).encode(), HEADERS)
    return json.load(urllib.request.urlopen(req, timeout=900))


def run_tests(task_dir, work, pattern=ALL_TESTS):
    for f in glob.glob(os.path.join(task_dir, "tests", pattern)):
        shutil.copy(f, work)  # overwrite with the originals every time
    try:
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", pattern],
                           cwd=work, capture_output=True, text=True, timeout=60)
        return r.returncode == 0, (r.stdout + r.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        return False, "tests timed out (60s)"


def inside(work, path):
    full = os.path.realpath(os.path.join(work, path))
    return full if full.startswith(os.path.realpath(work) + os.sep) else None


def call_tool(name, raw_args, task_dir, work, test_pattern):
    """(result text, is_error)"""
    try:
        a = json.loads(raw_args or "{}")
    except ValueError:
        return "error: arguments are not valid JSON", True
    if name == "list_files":
        return "\n".join(sorted(os.path.relpath(os.path.join(d, f), work) for d, _, fs in os.walk(work) for f in fs)), False
    if name == "run_tests":
        ok, out = run_tests(task_dir, work, test_pattern)
        return ("PASSED\n" if ok else "FAILED\n") + out, False
    if name in ("read_file", "write_file"):
        path = inside(work, a.get("path", ""))
        if not path:
            return "error: invalid path", True
        if name == "read_file":
            if not os.path.isfile(path):
                return "error: file not found", False
            return open(path).read(), False
        if "content" not in a:
            return "error: missing content", True
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write(a["content"])
        return "ok", False
    return "error: unknown tool " + name, True


def reported(work):
    """(number of findings, set of CWE ids) from FINDINGS.json, or None if missing or unreadable."""
    try:
        data = json.load(open(os.path.join(work, "FINDINGS.json")))
    except (OSError, ValueError):
        return None
    items = data.get("findings") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return None
    cwes = {"CWE-" + n for n in re.findall(r"CWE[-_ ]?(\d+)", json.dumps(items), re.I)}
    return len(items), cwes


def grade(task_dir, work, stat):
    expected_path = os.path.join(task_dir, "expected.json")
    if not os.path.isfile(expected_path):
        stat["passed"] = run_tests(task_dir, work)[0]
        return
    expected = {c.upper() for c in json.load(open(expected_path))["cwe"]}
    found = reported(work)
    stat["report"] = found is not None
    n_found, cwes = found or (0, set())
    stat["func"] = run_tests(task_dir, work, FUNC_TESTS)[0]
    if expected:
        stat["found"] = bool(cwes & expected)
        stat["fixed"] = run_tests(task_dir, work, SEC_TESTS)[0]
        stat["passed"] = stat["func"] and stat["fixed"]
    else:
        stat["false_alarm"] = n_found > 0
        stat["passed"] = stat["func"] and not stat["false_alarm"]


def solve(task_dir):
    work = tempfile.mkdtemp(prefix="eval-")
    shutil.copytree(os.path.join(task_dir, "files"), work, dirs_exist_ok=True)
    security = os.path.isfile(os.path.join(task_dir, "expected.json"))
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": open(os.path.join(task_dir, "task.md")).read()}]
    stat = {"turns": 0, "tool_calls": 0, "tool_errors": 0, "tokens": 0, "error": "",
            "func": None, "found": None, "fixed": None, "false_alarm": None, "report": None}
    t0 = time.time()
    try:
        for _ in range(args.max_turns):
            d = chat(messages)
            stat["turns"] += 1
            stat["tokens"] += d.get("usage", {}).get("total_tokens", 0)
            m = d["choices"][0]["message"]
            calls = m.get("tool_calls") or []
            messages.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": calls} if calls
                            else {"role": "assistant", "content": m.get("content") or ""})
            if not calls:
                break
            for c in calls:
                result, bad = call_tool(c["function"]["name"], c["function"].get("arguments"), task_dir, work,
                                        FUNC_TESTS if security else ALL_TESTS)
                stat["tool_calls"] += 1
                stat["tool_errors"] += bad
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
    except Exception as e:  # noqa: BLE001
        stat["error"] = str(e)[:150]
    grade(task_dir, work, stat)
    stat["seconds"] = time.time() - t0
    shutil.rmtree(work, ignore_errors=True)
    return stat


def mark(value, yes="yes", no="no"):
    return "-" if value is None else (yes if value else no)


tasks = sorted(d for d in glob.glob(os.path.join(args.tasks, "*")) if os.path.isfile(os.path.join(d, "task.md")))
if args.only:
    tasks = [t for t in tasks if os.path.basename(t) in args.only.split(",")]
print("model {} | {} tasks in {}\n".format(MODEL, len(tasks), args.tasks))
print("{:<22} {:>6} {:>7} {:>5} {:>5} {:>6} {:>5} {:>5}".format(
    "task", "result", "time(s)", "turns", "t.err", "found", "fixed", "func"))
rows = []
for t in tasks:
    s = solve(t)
    s["task"] = os.path.basename(t)
    rows.append(s)
    found = mark(s["found"]) if s["false_alarm"] is None else mark(s["false_alarm"], "ALARM", "none")
    print("{:<22} {:>6} {:>7.0f} {:>5} {:>5} {:>6} {:>5} {:>5}  {}".format(
        s["task"][:22], "PASS" if s["passed"] else "FAIL", s["seconds"], s["turns"], s["tool_errors"],
        found, mark(s["fixed"]), mark(s["func"]), s["error"]), flush=True)

n = len(rows)
passed = sum(r["passed"] for r in rows)
summary = {
    "date": time.strftime("%Y-%m-%d %H:%M"), "model": MODEL, "tasks": n, "passed": passed,
    "pass_rate": round(passed / n * 100, 1) if n else 0,
    "avg_seconds": round(sum(r["seconds"] for r in rows) / n, 1) if n else 0,
    "tool_errors": sum(r["tool_errors"] for r in rows),
    "tokens": sum(r["tokens"] for r in rows),
}
vulnerable = [r for r in rows if r["fixed"] is not None]
clean = [r for r in rows if r["false_alarm"] is not None]
security = vulnerable or clean
if security:
    pct = lambda k, of: round(k / of * 100, 1) if of else 0  # noqa: E731
    summary.update(
        vulnerable=len(vulnerable), detect_rate=pct(sum(r["found"] for r in vulnerable), len(vulnerable)),
        fix_rate=pct(sum(r["fixed"] for r in vulnerable), len(vulnerable)),
        regressions=sum(not r["func"] for r in vulnerable + clean),
        clean=len(clean), false_alarms=sum(r["false_alarm"] for r in clean),
        no_report=sum(not r["report"] for r in vulnerable + clean))
print("\npassed {}/{} ({}%), avg {}s per task, {} tool call failures".format(
    passed, n, summary["pass_rate"], summary["avg_seconds"], summary["tool_errors"]))
if security:
    print("detected {detect_rate}% and fixed {fix_rate}% of {vulnerable} vulnerable tasks, "
          "broke behavior in {regressions}".format(**summary))
    print("false alarms on {false_alarms} of {clean} clean tasks, "
          "no FINDINGS.json in {no_report} tasks".format(**summary))

task_set = os.path.basename(os.path.normpath(args.tasks))
suffix = "" if task_set == "tasks" else "-" + task_set
os.makedirs(args.out, exist_ok=True)
with open(os.path.join(args.out, MODEL + suffix + ".json"), "w") as f:
    json.dump({"summary": summary, "tasks": rows}, f, ensure_ascii=False, indent=1)
path = os.path.join(args.out, "summary" + suffix + ".csv")
new = not os.path.exists(path)
with open(path, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(summary))
    if new:
        w.writeheader()
    w.writerow(summary)

# latest result per model, as a comparison table
latest = {}
for r in csv.DictReader(open(path)):
    latest[r["model"]] = r
print("\nmodel comparison ({})".format(path))
if security:
    print("| model | pass | detect | fix | broke | false alarm | time/task | date |\n|---|---|---|---|---|---|---|---|")
    line = ("| {model} | {pass_rate}% | {detect_rate}% | {fix_rate}% | {regressions} | {false_alarms}/{clean} "
            "| {avg_seconds}s | {date} |")
else:
    print("| model | pass rate | time per task | tool errors | tokens | date |\n|---|---|---|---|---|---|")
    line = "| {model} | {pass_rate}% ({passed}/{tasks}) | {avg_seconds}s | {tool_errors} | {tokens} | {date} |"
for r in sorted(latest.values(), key=lambda r: -float(r["pass_rate"])):
    print(line.format(**r))
