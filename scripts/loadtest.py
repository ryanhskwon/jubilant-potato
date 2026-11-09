#!/usr/bin/env python3
"""Measure latency and throughput while raising the number of concurrent users, and find
the max concurrent users that meets the target (first-token p95 <= --ttft s, per user >= --tps tok/s).

e.g. ./serve.sh loadtest --users 1,4,8,16 --input 8000 --output 512 --ttft 3 --tps 20
"""
import argparse
import json
import os
import random
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

p = argparse.ArgumentParser()
p.add_argument("--users", default="1,2,4,8,16,32", help="concurrent user steps")
p.add_argument("--input", type=int, default=4000, help="input tokens per request (approx., 75%% shared by all requests)")
p.add_argument("--output", type=int, default=256, help="output tokens per request")
p.add_argument("--rounds", type=int, default=3, help="requests each user sends per step")
p.add_argument("--ttft", type=float, default=5.0, help="target: first-token p95 (seconds)")
p.add_argument("--tps", type=float, default=15.0, help="target: output speed per user (tok/s)")
p.add_argument("--csv", default="", help="path to save results as CSV")
args = p.parse_args()

URL = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1")
HEADERS = {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("VLLM_API_KEY", "")}
MODEL = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/models", headers=HEADERS), timeout=10))["data"][0]["id"]


def code(tokens):
    """Code text of about `tokens` tokens (1 token ~ 3.5 chars)."""
    line = "def f_{0}(x):\n    return x * {0} + {1}\n\n"
    return "".join(line.format(i, random.randint(0, 99)) for i in range(int(tokens * 3.5 / 40)))


SHARED = code(args.input * 0.75)  # shared by all requests (acts as system prompt / repo context -> prefix cache target)


def one(_):
    body = {
        "model": MODEL, "stream": True, "max_tokens": args.output, "min_tokens": args.output, "ignore_eos": True,
        "stream_options": {"include_usage": True},
        "messages": [{"role": "system", "content": SHARED},
                     {"role": "user", "content": code(args.input * 0.25) + "\nReview this code. #" + str(random.random())}],
    }
    t0, first, n = time.time(), None, 0
    req = urllib.request.Request(URL + "/chat/completions", json.dumps(body).encode(), HEADERS)
    for line in urllib.request.urlopen(req, timeout=1800):
        if line.startswith(b"data: {"):
            d = json.loads(line[6:])
            n = (d.get("usage") or {}).get("completion_tokens", n)
            delta = (d.get("choices") or [{}])[0].get("delta", {})
            if first is None and any(delta.get(k) for k in ("content", "reasoning_content", "reasoning")):
                first = time.time()
    end = time.time()
    first = first or end
    return first - t0, n / max(end - first, 1e-6), n


def pct(values, q):
    s = sorted(values)
    return s[min(int(len(s) * q / 100), len(s) - 1)] if s else 0.0


print("model {} | input {} / output {} tokens | target: first-token p95 <= {}s, per user >= {} tok/s\n".format(
    MODEL, args.input, args.output, args.ttft, args.tps))
print("{:>6} {:>12} {:>12} {:>14} {:>14} {:>6}".format("users", "TTFT p50", "TTFT p95", "tok/s per user", "total tok/s", "target"))
one(0)  # warm-up (loads the shared part into the cache)
rows, best = [], None
for users in [int(x) for x in args.users.split(",")]:
    t0 = time.time()
    with ThreadPoolExecutor(users) as ex:
        res = list(ex.map(one, range(users * args.rounds)))
    wall = time.time() - t0
    ttft, tps = [r[0] for r in res], [r[1] for r in res]
    row = dict(users=users, ttft_p50=pct(ttft, 50), ttft_p95=pct(ttft, 95), tps_user=pct(tps, 50),
               tps_total=sum(r[2] for r in res) / wall)
    row["ok"] = row["ttft_p95"] <= args.ttft and pct(tps, 5) >= args.tps
    rows.append(row)
    if row["ok"]:
        best = row
    print("{users:>6} {ttft_p50:>11.2f}s {ttft_p95:>11.2f}s {tps_user:>14.1f} {tps_total:>14.0f} {0:>6}".format(
        "OK" if row["ok"] else "X", **row), flush=True)
    if not row["ok"] and len(rows) > 1 and not rows[-2]["ok"]:
        break  # stop after two consecutive steps miss the target

print()
if best:
    print("max concurrent users meeting the target: {users} ({tps_user:.1f} tok/s per user, {tps_total:.0f} tok/s total)".format(**best))
else:
    print("no step met the target (relax --ttft, --tps or reduce --input)")
if args.csv:
    with open(args.csv, "w") as f:
        f.write("users,ttft_p50,ttft_p95,tps_user,tps_total,ok\n")
        f.writelines("{users},{ttft_p50:.3f},{ttft_p95:.3f},{tps_user:.2f},{tps_total:.1f},{ok}\n".format(**r) for r in rows)
