#!/usr/bin/env python3
"""Round-trip time of a request that gives the GPU almost nothing to do.

A few input tokens, one output token, thinking off, one request at a time. What is
left is mostly the path to the server: network, gateway, HTTP and queueing. Run it
against a remote server to see how much of TTFT is not the GPU's work.

e.g. python scripts/latency.py --n 30
"""
import argparse
import json
import os
import time
import urllib.request

p = argparse.ArgumentParser()
p.add_argument("--n", type=int, default=30, help="number of requests")
args = p.parse_args()

URL = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1")
HEADERS = {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("VLLM_API_KEY", "")}
MODEL = os.environ.get("VLLM_MODEL") or json.load(
    urllib.request.urlopen(urllib.request.Request(URL + "/models", headers=HEADERS), timeout=10))["data"][0]["id"]
BODY = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 1,
                   "chat_template_kwargs": {"enable_thinking": False}}).encode()

times, errors = [], 0
for _ in range(args.n):
    t0 = time.time()
    try:
        urllib.request.urlopen(urllib.request.Request(URL + "/chat/completions", BODY, HEADERS), timeout=60).read()
        times.append(time.time() - t0)
    except Exception:  # noqa: BLE001
        errors += 1
times.sort()


def pct(q):
    return times[min(int(len(times) * q / 100), len(times) - 1)] if times else float("nan")


print("model {} | {} tiny requests, one at a time".format(MODEL, args.n))
print("round trip: min {:.2f}s  p50 {:.2f}s  p95 {:.2f}s  max {:.2f}s  errors {}".format(
    times[0] if times else float("nan"), pct(50), pct(95), times[-1] if times else float("nan"), errors))
print("this is time the GPU barely works on: compare it with TTFT from loadtest")
