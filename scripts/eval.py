#!/usr/bin/env python3
"""코딩 과제 평가: 실행 중인 모델이 도구로 과제를 풀고, 테스트 통과 여부로 채점한다.

과제 폴더 (evals/tasks/<이름>/)
  task.md   지시문
  files/    시작 코드 (모델이 작업할 폴더로 복사됨)
  tests/    test_*.py (채점용, 테스트 실행 때마다 새로 덮어써서 모델이 고칠 수 없음)

모델이 쓰는 도구: list_files, read_file, write_file, run_tests
결과: 과제별 통과·시간·도구 호출 실패 + results/eval/summary.csv에 모델별 한 줄 누적

예) ./serve.sh eval
    ./serve.sh eval --tasks evals/tasks --only fix-median,merge-intervals
"""
import argparse
import csv
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

p = argparse.ArgumentParser()
p.add_argument("--tasks", default="evals/tasks", help="과제 폴더")
p.add_argument("--only", default="", help="쉼표로 구분한 과제 이름만 실행")
p.add_argument("--max-turns", type=int, default=15, help="과제당 최대 모델 호출 수")
p.add_argument("--out", default="results/eval", help="결과 폴더")
args = p.parse_args()

URL = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1")
HEADERS = {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("VLLM_API_KEY", "")}
MODEL = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/models", headers=HEADERS), timeout=10))["data"][0]["id"]

SYSTEM = ("You are a coding agent working in a small repository. Use the tools to inspect files, edit them, "
          "and run the tests. Keep working until the tests pass, then reply with a one-line summary.")
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


def chat(messages):
    body = {"model": MODEL, "messages": messages, "tools": TOOLS, "max_tokens": 8192}
    req = urllib.request.Request(URL + "/chat/completions", json.dumps(body).encode(), HEADERS)
    return json.load(urllib.request.urlopen(req, timeout=900))


def run_tests(task_dir, work):
    for f in glob.glob(os.path.join(task_dir, "tests", "*.py")):
        shutil.copy(f, work)  # 매번 원본으로 덮어씀
    try:
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"],
                           cwd=work, capture_output=True, text=True, timeout=60)
        return r.returncode == 0, (r.stdout + r.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        return False, "테스트 시간 초과 (60초)"


def inside(work, path):
    full = os.path.realpath(os.path.join(work, path))
    return full if full.startswith(os.path.realpath(work) + os.sep) else None


def call_tool(name, raw_args, task_dir, work):
    """(결과 텍스트, 오류 여부)"""
    try:
        a = json.loads(raw_args or "{}")
    except ValueError:
        return "error: arguments are not valid JSON", True
    if name == "list_files":
        return "\n".join(sorted(os.path.relpath(os.path.join(d, f), work) for d, _, fs in os.walk(work) for f in fs)), False
    if name == "run_tests":
        ok, out = run_tests(task_dir, work)
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


def solve(task_dir):
    work = tempfile.mkdtemp(prefix="eval-")
    shutil.copytree(os.path.join(task_dir, "files"), work, dirs_exist_ok=True)
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": open(os.path.join(task_dir, "task.md")).read()}]
    stat = {"turns": 0, "tool_calls": 0, "tool_errors": 0, "tokens": 0, "error": ""}
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
                result, bad = call_tool(c["function"]["name"], c["function"].get("arguments"), task_dir, work)
                stat["tool_calls"] += 1
                stat["tool_errors"] += bad
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
    except Exception as e:  # noqa: BLE001
        stat["error"] = str(e)[:150]
    stat["passed"] = run_tests(task_dir, work)[0]
    stat["seconds"] = time.time() - t0
    shutil.rmtree(work, ignore_errors=True)
    return stat


tasks = sorted(d for d in glob.glob(os.path.join(args.tasks, "*")) if os.path.isfile(os.path.join(d, "task.md")))
if args.only:
    tasks = [t for t in tasks if os.path.basename(t) in args.only.split(",")]
print("모델 {} | 과제 {}개\n".format(MODEL, len(tasks)))
print("{:<24} {:>6} {:>7} {:>9} {:>10} {:>8}".format("과제", "결과", "시간(s)", "모델 호출", "도구 호출", "도구 실패"))
rows = []
for t in tasks:
    s = solve(t)
    s["task"] = os.path.basename(t)
    rows.append(s)
    print("{task:<24} {0:>6} {seconds:>7.0f} {turns:>9} {tool_calls:>10} {tool_errors:>8}  {error}".format(
        "PASS" if s["passed"] else "FAIL", **s), flush=True)

n = len(rows)
passed = sum(r["passed"] for r in rows)
summary = {
    "date": time.strftime("%Y-%m-%d %H:%M"), "model": MODEL, "tasks": n, "passed": passed,
    "pass_rate": round(passed / n * 100, 1) if n else 0,
    "avg_seconds": round(sum(r["seconds"] for r in rows) / n, 1) if n else 0,
    "tool_errors": sum(r["tool_errors"] for r in rows),
    "tokens": sum(r["tokens"] for r in rows),
}
print("\n통과 {}/{} ({}%), 과제당 평균 {}초, 도구 호출 실패 {}회".format(
    passed, n, summary["pass_rate"], summary["avg_seconds"], summary["tool_errors"]))

os.makedirs(args.out, exist_ok=True)
with open(os.path.join(args.out, MODEL + ".json"), "w") as f:
    json.dump({"summary": summary, "tasks": rows}, f, ensure_ascii=False, indent=1)
path = os.path.join(args.out, "summary.csv")
new = not os.path.exists(path)
with open(path, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(summary))
    if new:
        w.writeheader()
    w.writerow(summary)

# 모델별 최근 결과 비교표
latest = {}
for r in csv.DictReader(open(path)):
    latest[r["model"]] = r
print("\n모델 비교 ({})".format(path))
print("| 모델 | 통과율 | 과제당 시간 | 도구 실패 | 토큰 | 날짜 |\n|---|---|---|---|---|---|")
for r in sorted(latest.values(), key=lambda r: -float(r["pass_rate"])):
    print("| {model} | {pass_rate}% ({passed}/{tasks}) | {avg_seconds}s | {tool_errors} | {tokens} | {date} |".format(**r))
