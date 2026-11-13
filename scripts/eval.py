#!/usr/bin/env python3
"""Coding task eval: the running model solves tasks with tools and is graded by tests.

Task folder (<tasks>/<name>/)
  task.md         instructions
  files/          starting code (copied into the model's work folder)
  tests/          test_*.py for grading; recopied before every run so the model cannot change them
  expected.json   security tasks only: {"cwe": ["CWE-89", ...]}, or {"cwe": []} for code with no vulnerability
  solution/       reference fix, used only by scripts/check_tasks.py

When tests/test_func_*.py exist, the model's run_tests tool runs only those; the other tests run
only at grading. Security tasks hide tests/test_sec_*.py (the attack) this way and also grade
FINDINGS.json against expected.json. Coding tasks hide acceptance tests this way (evals/long) and
get a score: the share of the tests failing on the starting code that pass after the model's work
(a test it breaks counts against it), 100 when every test passes.

Tools the model uses: list_files, read_file, write_file, run_tests
Output: a row per task + one line per model appended to <out>/summary.csv (summary-<set>.csv
for task sets other than evals/tasks)

e.g. ./serve.sh eval
     ./serve.sh eval --tasks evals/vuln
     ./serve.sh eval --tasks evals/vuln --only sql-injection,xss
     ./serve.sh eval --tasks evals/long --max-turns 60 --time-limit 900
"""
import argparse
import csv
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

p = argparse.ArgumentParser()
p.add_argument("--tasks", default="evals/tasks", help="task folder")
p.add_argument("--only", default="", help="run only these comma-separated task names")
p.add_argument("--max-turns", type=int, default=15, help="max model calls per task")
p.add_argument("--time-limit", type=int, default=0,
               help="seconds per task (0 = none); then the work so far is graded")
p.add_argument("--out", default="results/eval", help="output folder")
p.add_argument("--no-thinking", action="store_true",
               help="send enable_thinking=false (Qwen3, Gemma 4 chat templates); results saved as <model>-nothink")
args = p.parse_args()

URL = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1")
HEADERS = {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("VLLM_API_KEY", "")}
MODEL = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/models", headers=HEADERS), timeout=10))["data"][0]["id"]
LABEL = MODEL + "-nothink" if args.no_thinking else MODEL

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


def chat(messages, timeout=900):
    body = {"model": MODEL, "messages": messages, "tools": TOOLS, "max_tokens": 16384}  # same as the team coding agent
    if args.no_thinking:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(URL + "/chat/completions", json.dumps(body).encode(), HEADERS)
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def run_tests(task_dir, work, pattern=ALL_TESTS):
    for f in glob.glob(os.path.join(task_dir, "tests", pattern)):
        shutil.copy(f, work)  # overwrite with the originals every time
    try:
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", pattern],
                           cwd=work, capture_output=True, text=True, timeout=60)
        return r.returncode == 0, r.stdout + r.stderr
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
        return ("PASSED\n" if ok else "FAILED\n") + out[-2000:], False
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


MAX_CWES = 3  # listing many CWE ids on one task is guessing, not detection


def cwe_ids(value):
    out = set()
    for v in value if isinstance(value, list) else [value]:
        if isinstance(v, int) and not isinstance(v, bool):
            out.add("CWE-%d" % v)
        elif isinstance(v, str):
            out |= {"CWE-%d" % int(n) for n in re.findall(r"(?:CWE[-_ ]?)?(\d+)", v, re.I)}
    return out


def reported(work):
    """(findings that name a CWE, set of CWE ids) from FINDINGS.json, or None if missing or unreadable."""
    try:
        data = json.load(open(os.path.join(work, "FINDINGS.json")))
    except (OSError, ValueError):
        return None
    items = data.get("findings") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return None
    ids = [cwe_ids(item.get("cwe")) for item in items if isinstance(item, dict)]
    return sum(1 for i in ids if i), set().union(*ids)


def tests_passed(task_dir, work):
    """(all passed, number of passing tests, failing test names); a test module that fails to
    import counts none."""
    ok, out = run_tests(task_dir, work)
    ran = re.search(r"Ran (\d+) test", out)
    failed = sum(int(n) for n in re.findall(r"(?:failures|errors)=(\d+)", out))
    names = ["{}.{}".format(c, t) for t, c in re.findall(r"^(?:FAIL|ERROR): (\S+) \(([\w.]+)\)", out, re.M)]
    return ok, int(ran.group(1)) - failed if ran else 0, names


def defined_tests(task_dir):
    # from the source, not from "Ran N": a module that fails to import shows up as one test
    return sum(len(re.findall(r"^\s+def test_", open(f).read(), re.M))
               for f in glob.glob(os.path.join(task_dir, "tests", ALL_TESTS)))


def baseline(task_dir):
    with tempfile.TemporaryDirectory() as start:
        shutil.copytree(os.path.join(task_dir, "files"), start, dirs_exist_ok=True)
        return tests_passed(task_dir, start)[1]


def grade(task_dir, work, stat):
    expected_path = os.path.join(task_dir, "expected.json")
    if not os.path.isfile(expected_path):
        ok, passing, stat["failed_tests"] = tests_passed(task_dir, work)
        total, base = defined_tests(task_dir), baseline(task_dir)
        stat["passed"] = ok
        stat["score"] = 100.0 if ok else round(100.0 * max(0, passing - base) / max(1, total - base), 1)
        return
    expected = {c.upper() for c in json.load(open(expected_path))["cwe"]}
    found = reported(work)
    stat["report"] = found is not None
    n_found, cwes = found or (0, set())
    stat["func"] = run_tests(task_dir, work, FUNC_TESTS)[0]
    if expected:
        stat["found"] = bool(cwes & expected) and len(cwes) <= MAX_CWES
        stat["fixed"] = stat["func"] and run_tests(task_dir, work, SEC_TESTS)[0]
        stat["passed"] = stat["fixed"] and stat["found"]
    else:
        stat["false_alarm"] = n_found > 0
        stat["passed"] = stat["func"] and stat["report"] and not stat["false_alarm"]


def solve(task_dir):
    work = tempfile.mkdtemp(prefix="eval-")
    shutil.copytree(os.path.join(task_dir, "files"), work, dirs_exist_ok=True)
    visible = FUNC_TESTS if glob.glob(os.path.join(task_dir, "tests", FUNC_TESTS)) else ALL_TESTS
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": open(os.path.join(task_dir, "task.md")).read()}]
    stat = {"turns": 0, "tool_calls": 0, "tool_errors": 0, "tokens": 0, "out_tokens": 0, "error": "",
            "func": None, "found": None, "fixed": None, "false_alarm": None, "report": None, "score": None}
    t0 = time.time()
    try:
        for _ in range(args.max_turns):
            left = args.time_limit - (time.time() - t0) if args.time_limit else 900
            if left <= 0:
                stat["error"] = "time limit"
                break
            try:
                d = chat(messages, timeout=max(1, min(900, left)))
            except socket.timeout:
                if not args.time_limit:
                    raise
                stat["error"] = "time limit"
                break
            stat["turns"] += 1
            stat["tokens"] += d.get("usage", {}).get("total_tokens", 0)
            stat["out_tokens"] += d.get("usage", {}).get("completion_tokens", 0)  # thinking included
            m = d["choices"][0]["message"]
            calls = m.get("tool_calls") or []
            messages.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": calls} if calls
                            else {"role": "assistant", "content": m.get("content") or ""})
            if not calls:
                break
            for c in calls:
                result, bad = call_tool(c["function"]["name"], c["function"].get("arguments"), task_dir, work,
                                        visible)
                stat["tool_calls"] += 1
                stat["tool_errors"] += bad
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
    except Exception as e:  # noqa: BLE001
        stat["error"] = str(e)[:150]
    grade(task_dir, work, stat)
    stat["seconds"] = time.time() - t0
    if stat["score"] is not None:  # keep the model's code to see what it missed
        keep = os.path.join(args.out, "work", LABEL + "-" + os.path.basename(task_dir))
        shutil.rmtree(keep, ignore_errors=True)
        shutil.copytree(work, keep, ignore=shutil.ignore_patterns("test_*.py", "__pycache__"))
    shutil.rmtree(work, ignore_errors=True)
    return stat


def mark(value, yes="yes", no="no"):
    return "-" if value is None else (yes if value else no)


tasks = sorted(d for d in glob.glob(os.path.join(args.tasks, "*")) if os.path.isfile(os.path.join(d, "task.md")))
if args.only:
    tasks = [t for t in tasks if os.path.basename(t) in args.only.split(",")]
print("model {} | {} tasks in {}\n".format(LABEL, len(tasks), args.tasks))
print("{:<22} {:>6} {:>7} {:>5} {:>5} {:>6} {:>5} {:>5} {:>5}".format(
    "task", "result", "time(s)", "turns", "t.err", "found", "fixed", "func", "score"))
rows = []
for t in tasks:
    s = solve(t)
    s["task"] = os.path.basename(t)
    rows.append(s)
    found = mark(s["found"]) if s["false_alarm"] is None else mark(s["false_alarm"], "ALARM", "none")
    print("{:<22} {:>6} {:>7.0f} {:>5} {:>5} {:>6} {:>5} {:>5} {:>5}  {}".format(
        s["task"][:22], "PASS" if s["passed"] else "FAIL", s["seconds"], s["turns"], s["tool_errors"],
        found, mark(s["fixed"]), mark(s["func"]), "-" if s["score"] is None else "{:.0f}".format(s["score"]),
        s["error"]), flush=True)
    if s["score"] is not None:
        print("    output {} tokens in {:.0f}s ({:.0f} tok/s overall)".format(
            s["out_tokens"], s["seconds"], s["out_tokens"] / max(s["seconds"], 1e-6)))
    for name in s.get("failed_tests") or []:
        print("    failed: " + name)

n = len(rows)
passed = sum(r["passed"] for r in rows)
summary = {
    "date": time.strftime("%Y-%m-%d %H:%M"), "model": LABEL, "tasks": n, "passed": passed,
    "pass_rate": round(passed / n * 100, 1) if n else 0,
    "avg_seconds": round(sum(r["seconds"] for r in rows) / n, 1) if n else 0,
    "tool_errors": sum(r["tool_errors"] for r in rows),
    "tokens": sum(r["tokens"] for r in rows),
}
scored = [r["score"] for r in rows if r["score"] is not None]
if scored:
    summary["score"] = round(sum(scored) / len(scored), 1)
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
if scored:
    print("score {} (share of the requested work whose tests pass, 0-100)".format(summary["score"]))
if security:
    print("detected {detect_rate}% and fixed {fix_rate}% of {vulnerable} vulnerable tasks, "
          "broke behavior in {regressions}".format(**summary))
    print("false alarms on {false_alarms} of {clean} clean tasks, "
          "no FINDINGS.json in {no_report} tasks".format(**summary))

task_set = os.path.basename(os.path.normpath(args.tasks))
suffix = "" if task_set == "tasks" else "-" + task_set
os.makedirs(args.out, exist_ok=True)
with open(os.path.join(args.out, LABEL + suffix + ".json"), "w") as f:
    json.dump({"summary": summary, "tasks": rows}, f, ensure_ascii=False, indent=1)
summary["task_ids"] = ",".join(sorted(r["task"] for r in rows))
path = os.path.join(args.out, "summary" + suffix + ".csv")
if os.path.exists(path):
    with open(path, newline="") as f:
        if next(csv.reader(f), []) != list(summary):
            os.replace(path, path + ".old")  # written by an older eval.py with other columns
new = not os.path.exists(path)
with open(path, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(summary))
    if new:
        w.writeheader()
    w.writerow(summary)

latest = {}
for r in csv.DictReader(open(path)):
    if r["task_ids"] == summary["task_ids"]:
        latest[r["model"]] = r
print("\nmodel comparison, runs on the same {} tasks ({})".format(n, path))
if security:
    print("| model | pass | detect | fix | broke | false alarm | time/task | date |\n|---|---|---|---|---|---|---|---|")
    line = ("| {model} | {pass_rate}% | {detect_rate}% | {fix_rate}% | {regressions} | {false_alarms}/{clean} "
            "| {avg_seconds}s | {date} |")
else:
    print("| model | pass rate | score | time per task | tool errors | tokens | date |\n|---|---|---|---|---|---|---|")
    line = ("| {model} | {pass_rate}% ({passed}/{tasks}) | {score} | {avg_seconds}s | {tool_errors} | {tokens} "
            "| {date} |")
for r in sorted(latest.values(), key=lambda r: -float(r["pass_rate"])):
    print(line.format(**r))
