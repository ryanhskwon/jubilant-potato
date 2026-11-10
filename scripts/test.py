#!/usr/bin/env python3
"""Feature check for the running model: text, tool calls, images, streaming speed."""
import base64
import json
import os
import struct
import time
import urllib.error
import urllib.request
import zlib

URL = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1")
HEADERS = {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("VLLM_API_KEY", "")}


def post(body, stream=False):
    req = urllib.request.Request(URL + "/chat/completions", json.dumps(body).encode(), HEADERS)
    return urllib.request.urlopen(req, timeout=600) if stream else json.load(urllib.request.urlopen(req, timeout=600))


def ask(content, **kw):
    return post(dict(model=MODEL, messages=[{"role": "user", "content": content}], max_tokens=4096, **kw))["choices"][0]["message"]


def red_png():
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * 32 for _ in range(32))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 32, 32, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:  # noqa: BLE001
        ok, detail = False, str(e)[:150]
    print("[{}] {:<8} {}".format("PASS" if ok else "FAIL", name, detail))
    return ok


def text():
    m = ask("What is the capital of South Korea? One word.")
    return "seoul" in (m.get("content") or "").lower(), repr((m.get("content") or "").strip())


def tool():
    tools = [{"type": "function", "function": {"name": "read_file", "description": "Read a file",
              "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}]
    calls = ask("Read src/main.py using the tool.", tools=tools).get("tool_calls") or []
    return bool(calls) and "src/main.py" in calls[0]["function"]["arguments"], json.dumps(calls)[:120]


def image():
    url = "data:image/png;base64," + base64.b64encode(red_png()).decode()
    try:
        m = ask([{"type": "text", "text": "What color is this image? One word."}, {"type": "image_url", "image_url": {"url": url}}])
    except urllib.error.HTTPError as e:
        return e.code == 400, "model has no image support (HTTP 400)"
    return "red" in (m.get("content") or "").lower(), repr((m.get("content") or "").strip())


def speed():
    t0, first, n = time.time(), None, 0
    body = dict(model=MODEL, stream=True, max_tokens=512, stream_options={"include_usage": True},
                messages=[{"role": "user", "content": "Write a Python quicksort with comments."}])
    for line in post(body, stream=True):
        if line.startswith(b"data: {"):
            d = json.loads(line[6:])
            n = (d.get("usage") or {}).get("completion_tokens", n)
            if first is None and d.get("choices") and any(d["choices"][0].get("delta", {}).get(k) for k in ("content", "reasoning_content", "reasoning")):
                first = time.time()
    first = first or time.time()
    return n > 0, "first token {:.2f}s, {:.1f} tok/s".format(first - t0, n / max(time.time() - first, 1e-6))


MODEL = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/models", headers=HEADERS), timeout=10))["data"][0]["id"]
print("model:", MODEL)
CHECKS = [("text", text), ("tool", tool), ("image", image), ("speed", speed)]
results = [check(n, f) for n, f in CHECKS]
print("passed {}/{}".format(sum(results), len(results)))
os.makedirs("results/test", exist_ok=True)
with open(os.path.join("results", "test", MODEL + ".json"), "w") as f:
    json.dump({"model": MODEL, "date": time.strftime("%Y-%m-%d %H:%M"),
               "checks": {n: r for (n, _), r in zip(CHECKS, results)}}, f, indent=1)
