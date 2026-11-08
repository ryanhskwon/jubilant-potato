#!/usr/bin/env python3
"""동시 사용자 수를 늘려 가며 응답 속도와 처리량을 측정하고,
목표(첫 토큰 p95 ≤ --ttft 초, 사용자당 ≥ --tps tok/s)를 지키는 최대 동시 사용자를 찾는다.

예) ./serve.sh loadtest --users 1,4,8,16 --input 8000 --output 512 --ttft 3 --tps 20
"""
import argparse
import json
import os
import random
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

p = argparse.ArgumentParser()
p.add_argument("--users", default="1,2,4,8,16,32", help="동시 사용자 수 단계")
p.add_argument("--input", type=int, default=4000, help="요청당 입력 토큰 (대략, 75%%는 모든 요청 공통)")
p.add_argument("--output", type=int, default=256, help="요청당 출력 토큰")
p.add_argument("--rounds", type=int, default=3, help="단계마다 사용자 1명이 보내는 요청 수")
p.add_argument("--ttft", type=float, default=5.0, help="목표: 첫 토큰 p95 (초)")
p.add_argument("--tps", type=float, default=15.0, help="목표: 사용자당 출력 속도 (tok/s)")
p.add_argument("--csv", default="", help="결과를 CSV로 저장할 경로")
args = p.parse_args()

URL = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1")
HEADERS = {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("VLLM_API_KEY", "")}
MODEL = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/models", headers=HEADERS), timeout=10))["data"][0]["id"]


def code(tokens):
    """약 tokens 토큰 분량의 코드 텍스트 (1토큰 ≈ 3.5자)."""
    line = "def f_{0}(x):\n    return x * {0} + {1}\n\n"
    return "".join(line.format(i, random.randint(0, 99)) for i in range(int(tokens * 3.5 / 40)))


SHARED = code(args.input * 0.75)  # 모든 요청 공통 (시스템 프롬프트·저장소 컨텍스트 역할 → prefix cache 대상)


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


print("모델 {} | 입력 {} / 출력 {} 토큰 | 목표: 첫 토큰 p95 ≤ {}초, 사용자당 ≥ {} tok/s\n".format(
    MODEL, args.input, args.output, args.ttft, args.tps))
print("{:>6} {:>12} {:>12} {:>14} {:>14} {:>6}".format("동시", "첫토큰 p50", "첫토큰 p95", "사용자당 tok/s", "전체 tok/s", "목표"))
one(0)  # 워밍업 (공통 부분을 캐시에 올림)
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
        break  # 두 단계 연속 목표 미달이면 중단

print()
if best:
    print("목표를 지키는 최대 동시 사용자: {users}명 (사용자당 {tps_user:.1f} tok/s, 전체 {tps_total:.0f} tok/s)".format(**best))
else:
    print("목표를 지킨 단계가 없음 (--ttft, --tps 완화 또는 --input 축소)")
if args.csv:
    with open(args.csv, "w") as f:
        f.write("users,ttft_p50,ttft_p95,tps_user,tps_total,ok\n")
        f.writelines("{users},{ttft_p50:.3f},{ttft_p95:.3f},{tps_user:.2f},{tps_total:.1f},{ok}\n".format(**r) for r in rows)
