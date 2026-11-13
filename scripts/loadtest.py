#!/usr/bin/env python3
"""Capacity test shaped like a vulnerability scan + fix agent.

Each simulated user runs scan sessions back to back. A session starts from the user's own
code (real .py files from this machine's Python install, about --context tokens) and makes
--turns model calls. Every turn appends the model's answer and a tool result (more code,
about --tool-output tokens), so the prompt grows like a real agent and the prefix cache
only helps within a session. Concurrency steps up through --users, --duration s per step.

Output: TTFT, output tok/s per request, latency, server KV cache and queue per step, then
max concurrent sessions under the target, sessions per hour and registered users.
Saved to results/loadtest/<model>-<date>.txt and .csv.

e.g. ./serve.sh loadtest
     ./serve.sh loadtest --users 4,8,16 --duration 120 --context 30000
"""
import argparse
import csv
import glob
import json
import os
import random
import subprocess
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

p = argparse.ArgumentParser()
p.add_argument("--users", default="1,2,4,6,8,12,16", help="concurrent sessions per step")
p.add_argument("--duration", type=int, default=180, help="seconds per step")
p.add_argument("--context", type=int, default=20000, help="code tokens at the start of a session")
p.add_argument("--turns", type=int, default=8, help="model calls per session")
p.add_argument("--output", type=int, default=512, help="output tokens per call")
p.add_argument("--natural", action="store_true",
               help="let the model stop on its own (up to 4096 tokens per call) to see real wait times")
p.add_argument("--tool-output", type=int, default=1000, help="code tokens added per turn as a tool result")
p.add_argument("--ttft", type=float, default=5.0, help="target: TTFT p95 (seconds)")
p.add_argument("--tps", type=float, default=20.0, help="target: 95%% of calls at least this many output tok/s")
p.add_argument("--batch-sessions", type=int, default=0, help="sessions reserved for daytime batch jobs")
p.add_argument("--csv", default="", help="CSV path (default: next to the .txt report)")
p.add_argument("--out", default="results/loadtest", help="report folder")
args = p.parse_args()

URL = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1")
BASE = URL[:-3] if URL.endswith("/v1") else URL
HEADERS = {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("VLLM_API_KEY", "")}
MODEL = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/models", headers=HEADERS), timeout=10))["data"][0]["id"]
FIRST_TOKEN_KEYS = ("content", "reasoning_content", "reasoning")
SYSTEM = ("You are a security engineer agent. Find vulnerabilities in the user's code, name each with its CWE, "
          "and write patches that fix them without changing behavior. Ask for more files with tools when needed.")
STOP = threading.Event()

SRC = os.path.dirname(os.__file__)
SKIP_DIRS = {"encodings", "test", "tests", "idlelib", "lib2to3", "pydoc_data", "site-packages", "dist-packages"}
CHARS_PER_TOKEN = 3.5
NATURAL_CAP = 4096


def plain(text):
    """Ordinary code: codec tables and escape-heavy data files pack 2-3x more tokens per char."""
    n = max(len(text), 1)
    return len(text.encode("utf-8")) - len(text) < n / 100 and text.count("\\") < n / 100


CORPUS = []
for path in sorted(glob.glob(os.path.join(SRC, "**", "*.py"), recursive=True)):
    rel = os.path.relpath(path, SRC)
    if SKIP_DIRS & set(rel.split(os.sep)[:-1]) or os.path.getsize(path) < 2000:
        continue
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if plain(text):
        CORPUS.append((rel, text))
if not CORPUS:
    raise SystemExit("no usable .py files found under " + SRC)


def code(tokens, rng):
    """Real source files concatenated to about `tokens` tokens; the same rng seed gives every model the same text."""
    budget = int(tokens * CHARS_PER_TOKEN)
    parts, size = [], 0
    while size < budget:
        rel, text = rng.choice(CORPUS)
        part = "### File: {}\n{}".format(rel, text)[:budget - size]
        parts.append(part)
        size += len(part)
    return "\n\n".join(parts)


def call(messages, max_tokens, fixed=True):
    body = {"model": MODEL, "messages": messages, "stream": True, "stream_options": {"include_usage": True},
            "max_tokens": max_tokens}
    if fixed:
        body.update(min_tokens=max_tokens, ignore_eos=True)
    t0, first, n_out, n_in, text = time.time(), None, 0, 0, []
    try:
        req = urllib.request.Request(URL + "/chat/completions", json.dumps(body).encode(), HEADERS)
        for line in urllib.request.urlopen(req, timeout=1800):
            if not line.startswith(b"data: {"):
                continue
            d = json.loads(line[6:])
            usage = d.get("usage") or {}
            n_out = usage.get("completion_tokens", n_out)
            n_in = usage.get("prompt_tokens", n_in)
            delta = (d.get("choices") or [{}])[0].get("delta") or {}
            if first is None and any(delta.get(k) for k in FIRST_TOKEN_KEYS):
                first = time.time()
            if delta.get("content"):
                text.append(delta["content"])
    except Exception as e:  # noqa: BLE001
        return {"err": str(e)[:100]}
    end = time.time()
    first = first or end
    return {"err": "", "ttft": first - t0, "e2e": end - t0, "n_out": n_out, "n_in": n_in, "text": "".join(text),
            "tps": (n_out - 1) / (end - first) if n_out > 1 and end > first else 0.0}


def user(idx, users, deadline, results):
    rng = random.Random("{}-{}".format(users, idx))
    time.sleep(rng.uniform(0, min(10, args.duration / 10)))
    while time.time() < deadline and not STOP.is_set():
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": "Scan this code for security vulnerabilities and fix them.\n\n" +
                     code(args.context, rng)}]
        for _ in range(args.turns):
            if time.time() >= deadline or STOP.is_set():
                return
            r = call(messages, NATURAL_CAP if args.natural else args.output, fixed=not args.natural)
            results.append(r)
            if r["err"]:
                time.sleep(1)
                break
            messages.append({"role": "assistant", "content": r["text"] or "(no text)"})
            messages.append({"role": "user", "content": "Tool result (read_file):\n" + code(args.tool_output, rng)})


def scrape():
    try:
        req = urllib.request.Request(BASE + "/metrics", headers=HEADERS)
        text = urllib.request.urlopen(req, timeout=5).read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return {}
    vals = {}
    for line in text.splitlines():
        if not line.startswith("vllm:"):
            continue
        fields = line.split("}")[-1].split() if "}" in line else line.split()[1:]
        try:
            v = float(fields[0])
        except (IndexError, ValueError):
            continue
        name = line.split("{")[0].split()[0]
        vals[name] = vals.get(name, 0.0) + v
    return vals


GAUGES = ("vllm:kv_cache_usage_perc", "vllm:gpu_cache_usage_perc", "vllm:num_requests_waiting",
          "vllm:num_requests_running")


GPU_FIELDS = ("util", "power", "temp", "clock", "mem")


def gpu_now():
    """(util %, power W, temp C, SM clock MHz, memory used MiB) of the first GPU, or None."""
    try:
        line = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,power.draw,temperature.gpu,clocks.sm,memory.used",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout.splitlines()[0]
        return tuple(float(v) for v in line.split(","))
    except (OSError, IndexError, ValueError, subprocess.SubprocessError):
        return None


def sample(stop, srv):
    srv["start"], srv["gpu"] = scrape(), []
    while not stop.wait(1):
        s = scrape()
        if s:
            srv["end"] = s
        for k in GAUGES:
            if k in s:
                srv[k] = max(srv.get(k, 0.0), s[k])
        g = gpu_now()
        if g:
            srv["gpu"].append(g)
    srv["end"] = scrape() or srv.get("end", {})


def gpu_stats(samples):
    if not samples:
        return {"gpu_" + k: None for k in ("util", "power", "power_max", "temp_max", "clock", "clock_min", "mem_gb")}
    cols = dict(zip(GPU_FIELDS, zip(*samples)))
    avg = lambda k: sum(cols[k]) / len(cols[k])  # noqa: E731
    return {"gpu_util": avg("util"), "gpu_power": avg("power"), "gpu_power_max": max(cols["power"]),
            "gpu_temp_max": max(cols["temp"]), "gpu_clock": avg("clock"), "gpu_clock_min": min(cols["clock"]),
            "gpu_mem_gb": max(cols["mem"]) / 1024}


def delta(srv, name):
    a, b = srv.get("start", {}), srv.get("end", {})
    return b[name] - a[name] if name in a and name in b else None


def hist_avg(srv, name):
    total, count = delta(srv, name + "_sum"), delta(srv, name + "_count")
    return total / count if total is not None and count else None


def pct(values, q):
    s = sorted(values)
    return s[min(int(len(s) * q / 100), len(s) - 1)] if s else 0.0


def step(users):
    results, srv, stop = [], {}, threading.Event()
    sampler = threading.Thread(target=sample, args=(stop, srv), daemon=True)
    sampler.start()
    t0 = time.time()
    with ThreadPoolExecutor(users) as ex:
        list(ex.map(lambda i: user(i, users, t0 + args.duration, results), range(users)))
    wall = time.time() - t0
    stop.set()
    sampler.join()

    done = [r for r in results if not r["err"]]
    kv = srv.get("vllm:kv_cache_usage_perc", srv.get("vllm:gpu_cache_usage_perc"))
    if kv is not None and kv <= 1.0:
        kv *= 100
    hits, queries = delta(srv, "vllm:prefix_cache_hits_total"), delta(srv, "vllm:prefix_cache_queries_total")
    preempt = delta(srv, "vllm:num_preemptions_total")
    row = {
        "users": users, "requests": len(done), "errors": len(results) - len(done),
        "ttft_p50": pct([r["ttft"] for r in done], 50), "ttft_p95": pct([r["ttft"] for r in done], 95),
        "ttft_p99": pct([r["ttft"] for r in done], 99),
        "tps_p50": pct([r["tps"] for r in done], 50), "tps_p5": pct([r["tps"] for r in done], 5),
        "lat_p50": pct([r["e2e"] for r in done], 50), "lat_p95": pct([r["e2e"] for r in done], 95),
        "lat_mean": sum(r["e2e"] for r in done) / len(done) if done else 0.0,
        "in_tokens_avg": sum(r["n_in"] for r in done) / len(done) if done else 0.0,
        "out_tokens_avg": sum(r["n_out"] for r in done) / len(done) if done else 0.0,
        "out_tps": sum(r["n_out"] for r in done) / wall,
        "sessions_per_hour": len(done) / args.turns / wall * 3600,
        "kv_max": kv, "waiting_max": srv.get("vllm:num_requests_waiting"),
        "running_max": srv.get("vllm:num_requests_running"),
        "prefix_hit": hits / queries if hits is not None and queries else None, "preemptions": preempt,
        "prefill_tps": (queries - hits) / wall if hits is not None and queries is not None else None,
        "queue_avg": hist_avg(srv, "vllm:request_queue_time_seconds"),
        "prefill_avg": hist_avg(srv, "vllm:request_prefill_time_seconds"),
        "decode_avg": hist_avg(srv, "vllm:request_decode_time_seconds"),
    }
    row.update(gpu_stats(srv.get("gpu")))
    row["session_s"] = row["lat_mean"] * args.turns
    row["ok"] = bool(done) and not row["errors"] and row["ttft_p95"] <= args.ttft and row["tps_p5"] >= args.tps
    if (kv is not None and kv >= 90) or (preempt or 0) > 0:
        row["limit"] = "KV"
    elif (row["waiting_max"] or 0) > 0:
        row["limit"] = "seqs" if (row["running_max"] or 0) < users else "pref"
    else:
        row["limit"] = "-" if row["ok"] else "gpu"
    return row


def config_max_num_seqs():
    for path in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "configs", "*.yaml")):
        lines = [l.split("#")[0].strip() for l in open(path)]
        if "served-model-name: " + MODEL in lines:
            for l in lines:
                if l.startswith("max-num-seqs:"):
                    return int(l.split(":")[1])
    return None


os.makedirs(args.out, exist_ok=True)
stamp = time.strftime("%Y%m%d-%H%M")
report_path = os.path.join(args.out, "{}-{}.txt".format(MODEL, stamp))
csv_path = args.csv or os.path.join(args.out, "{}-{}.csv".format(MODEL, stamp))
report = open(report_path, "w")


def out(line=""):
    print(line, flush=True)
    report.write(line + "\n")
    report.flush()


max_seqs = config_max_num_seqs()
out("model {} | max-num-seqs {}".format(MODEL, max_seqs if max_seqs is not None else "?"))
out("session: {} tok code, {} calls x ({} + {} tool tok), {}s/step".format(
    args.context, args.turns, "out<={}".format(NATURAL_CAP) if args.natural else "{} out".format(args.output),
    args.tool_output, args.duration))
out("target: TTFT p95 <= {:g}s and 95% of calls >= {:g} tok/s (tok/s p5)".format(args.ttft, args.tps))
out("note: no pause between turns (worst case); MTP speedup depends on the code")

sample_text = code(4000, random.Random("warm-up"))
warm = call([{"role": "user", "content": sample_text}], 16)
if warm["err"]:
    raise SystemExit("warm-up failed: " + warm["err"])
out("warm-up ok, {} code files, {:.1f} chars per token with this tokenizer\n".format(
    len(CORPUS), len(sample_text) / warm["n_in"] if warm["n_in"] else 0))

out("{:>5} {:>8} {:>8} {:>8} {:>8} {:>8} {:>9} {:>5} {:>5} {:>4}".format(
    "users", "TTFT p50", "TTFT p95", "tok/s50", "tok/s p5", "lat p95", "out tok/s", "KV%", "limit", "SLO"))
rows = []
try:
    for n in [int(x) for x in args.users.split(",")]:
        r = step(n)
        rows.append(r)
        out("{users:>5} {ttft_p50:>7.2f}s {ttft_p95:>7.2f}s {tps_p50:>8.1f} {tps_p5:>8.1f} {lat_p95:>7.1f}s "
            "{out_tps:>9.0f} {kv:>5} {limit:>5} {ok:>4}{err}".format(
                kv="-" if r["kv_max"] is None else "{:.0f}".format(r["kv_max"]), ok="OK" if r["ok"] else "X",
                err="  errors {}".format(r["errors"]) if r["errors"] else "", **{k: v for k, v in r.items() if k != "ok"}))
        if not r["ok"] and len(rows) > 1 and not rows[-2]["ok"]:
            break  # two failing steps in a row: past the limit
except KeyboardInterrupt:
    STOP.set()
    out("stopped by Ctrl+C, summary of finished steps:")

with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["users"])
    w.writeheader()
    w.writerows(rows)

def cell(v, fmt):
    return "-" if v is None else fmt.format(v)


out()
out("SERVER BREAKDOWN (per call averages from vLLM /metrics; TTFT ~ queue + prefill)")
out("{:>5} {:>8} {:>8} {:>8} {:>9} {:>13} {:>7} {:>7}".format(
    "users", "queue", "prefill", "decode", "cache hit", "prefill tok/s", "running", "waiting"))
for r in rows:
    out("{:>5} {:>8} {:>8} {:>8} {:>9} {:>13} {:>7} {:>7}".format(
        r["users"], cell(r["queue_avg"], "{:.2f}s"), cell(r["prefill_avg"], "{:.2f}s"),
        cell(r["decode_avg"], "{:.1f}s"), cell(r["prefix_hit"] and r["prefix_hit"] * 100, "{:.0f}%"),
        cell(r["prefill_tps"], "{:.0f}"), cell(r["running_max"], "{:.0f}"), cell(r["waiting_max"], "{:.0f}")))
out("prefill tok/s = input tokens computed per second (cache hits excluded)")
out()
out("GPU (nvidia-smi every second during the step)")
out("{:>5} {:>6} {:>8} {:>8} {:>6} {:>9} {:>9} {:>8}".format(
    "users", "util", "power", "max W", "temp", "SM clock", "min clock", "VRAM"))
for r in rows:
    out("{:>5} {:>6} {:>8} {:>8} {:>6} {:>9} {:>9} {:>8}".format(
        r["users"], cell(r["gpu_util"], "{:.0f}%"), cell(r["gpu_power"], "{:.0f}W"),
        cell(r["gpu_power_max"], "{:.0f}W"), cell(r["gpu_temp_max"], "{:.0f}C"),
        cell(r["gpu_clock"], "{:.0f}MHz"), cell(r["gpu_clock_min"], "{:.0f}MHz"), cell(r["gpu_mem_gb"], "{:.1f}GB")))
out("util ~100% = GPU busy (more users only add waiting); a falling SM clock at high")
out("power or temp = throttling, which lowers tok/s")
out()
in_avg = sum(r["in_tokens_avg"] for r in rows) / len(rows) if rows else 0
out_avg = sum(r["out_tokens_avg"] for r in rows) / len(rows) if rows else 0
expected_in = args.context + (args.turns - 1) / 2 * (out_avg + args.tool_output)
out("tokens per call: {:.0f} in (target ~{:.0f}), {:.0f} out (avg, out includes thinking)".format(
    in_avg, expected_in, out_avg))
if rows and abs(in_avg / expected_in - 1) > 0.2:
    out("WARN: input is {:+.0f}% off the target; this tokenizer packs the same code".format(
        (in_avg / expected_in - 1) * 100))
    out("      differently, so this model did more or less work than the others.")
out("limit: KV = KV cache full, seqs = queue at max-num-seqs,")
out("       pref = new requests waiting for prefill (max-num-batched-tokens),")
out("       gpu = slow without a queue")
out()
best = max((r for r in rows if r["ok"]), key=lambda r: r["users"], default=None)
after = [r["users"] for r in rows if best and r["users"] > best["users"]]
if best:
    out("CAPACITY")
    out("  max concurrent sessions : {}{}".format(
        best["users"], " (limit is between {} and {})".format(best["users"], after[0]) if after else
        " (every step passed, try larger --users)"))
    out("  at that load            : TTFT p95 {:.1f}s, {:.0f} tok/s per call, latency p95 {:.1f}s".format(
        best["ttft_p95"], best["tps_p50"], best["lat_p95"]))
    out("  one scan + fix session  : {} calls, about {:.0f}s".format(args.turns, best["lat_mean"] * args.turns))
else:
    out("CAPACITY: no step met the target (relax --ttft / --tps or lower --context)")
if rows:
    top = max(rows, key=lambda r: r["sessions_per_hour"])
    out("  batch max throughput    : {:.0f} sessions/hour at {} concurrent (no target)".format(
        top["sessions_per_hour"], top["users"]))
if best:
    n = best["users"] - args.batch_sessions
    out("  registered users = interactive sessions / share of work time spent scanning")
    out("    " + ("" if after else "at least ") +
        "   ".join("{}% -> {}".format(s, max(0, int(n * 100 / s))) for s in (5, 10, 25, 50)))
    if args.batch_sessions:
        out("    ({} of {} sessions kept for batch jobs)".format(args.batch_sessions, best["users"]))
    if after:
        out("  suggested max-num-seqs  : {} (more requests wait instead of slowing everyone)".format(best["users"]))
first_fail = next((r for r in rows if not r["ok"]), None)
if first_fail and first_fail["limit"] == "seqs":
    out("  WARN: the server never ran more than {:.0f} calls at once (config says {}).".format(
        first_fail["running_max"] or 0, max_seqs))
    out("        Raise max-num-seqs in the model yaml or ./serve.sh up again, rerun.")
if first_fail and first_fail["limit"] == "pref":
    out("  NOTE: new sessions waited for prefill. To shorten TTFT, try")
    out("        max-num-batched-tokens: 16384 in the model yaml (tok/s p5 may drop).")
out()
out("saved: " + report_path)
out("       " + csv_path)
