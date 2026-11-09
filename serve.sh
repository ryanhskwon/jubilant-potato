#!/usr/bin/env bash
# vLLM model serving (1 GPU: one model at a time)
#
#   ./serve.sh list              list models (with numbers)
#   ./serve.sh check             check server, image and models
#   ./serve.sh key               create VLLM_API_KEY in .env (if empty) and show it
#   ./serve.sh up <name|number>  start a model, e.g. ./serve.sh up 2
#   ./serve.sh down              stop
#   ./serve.sh status            status
#   ./serve.sh logs              logs
#   ./serve.sh errors            error / memory / KV cache lines from the logs
#   ./serve.sh test              feature check
#   ./serve.sh loadtest [opts]   capacity: TTFT, tok/s, latency, how many users
#   ./serve.sh eval [opts]       coding task eval (pass rate) -> results/eval/
#   ./serve.sh test-all          test + loadtest + eval, all models -> results/
#   ./serve.sh monitor up|down   Grafana metrics collection
set -euo pipefail
cd "$(dirname "$0")"
[[ -f .env ]] && { set -a; . ./.env; set +a; }

IMAGE=${VLLM_IMAGE:-vllm/vllm-openai:v0.33.0}
MODELS_DIR=${MODELS_DIR:-/data/models}
export VLLM_URL=http://127.0.0.1:${HOST_PORT:-8000}/v1
PY=$(command -v python3 || echo /usr/libexec/platform-python)

# model name (= compose service, configs/<name>.yaml)   model folder (under MODELS_DIR)
MODELS="
qwen3.8-27b-fp8          Qwen3.8-27B-FP8
qwen3.8-27b-nvfp4        Qwen3.8-27B-NVFP4
qwen3.6-35b-a3b-fp8      Qwen3.6-35B-A3B-FP8
gemma-4-31b-it-fp8       gemma-4-31B-it-FP8-block
qwen3-coder-30b-a3b-fp8  Qwen3-Coder-30B-A3B-Instruct-FP8
qwen3-coder-next-fp8     Qwen3-Coder-Next-FP8
"
names()   { awk 'NF {print $1}' <<<"$MODELS"; }
dir_of()  { awk -v m="$1" '$1 == m {print $2}' <<<"$MODELS"; }
name_of() { if [[ $1 =~ ^[0-9]+$ ]]; then names | sed -n "${1}p"; else echo "$1"; fi; }
dc()      { docker compose --profile all "$@"; }
running() { dc ps --services --status running 2>/dev/null | head -1; }

case ${1:-} in
list)
  i=0
  for m in $(names); do
    i=$((i + 1))
    [[ -d $MODELS_DIR/$(dir_of "$m") ]] && s=present || s=missing
    printf '%2d  %-26s %-34s %s\n' "$i" "$m" "$(dir_of "$m")" "$s"
  done ;;

key)
  [[ -f .env ]] || cp .env.example .env
  if [[ -z ${VLLM_API_KEY:-} ]]; then
    VLLM_API_KEY=$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')
    grep -q '^VLLM_API_KEY=' .env || echo 'VLLM_API_KEY=' >> .env
    sed -i "s/^VLLM_API_KEY=.*/VLLM_API_KEY=$VLLM_API_KEY/" .env
    echo "new key saved to .env (apply it with ./serve.sh up <model>)"
  fi
  echo "VLLM_API_KEY: $(sed 's/..../& /g' <<<"$VLLM_API_KEY")"
  echo "(spaces are only for reading; type the key without them)" ;;

check)
  echo "[GPU]"
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
  drv=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
  (( ${drv%%.*} >= 580 )) || echo "  WARN: driver $drv - vLLM 0.33 (CUDA 13) needs R580 or newer"

  echo "[model folders]"
  dirs=()
  for m in $(names); do
    d=$MODELS_DIR/$(dir_of "$m")
    if [[ ! -d $d ]]; then echo "  $m: missing"; continue; fi
    if [[ -n $(find "$d" -maxdepth 1 -name '*.safetensors' -size -2k) ]]; then
      echo "  $m: only git-lfs pointers -> run git lfs pull in the folder"
    else
      echo "  $m: OK ($(du -sh --exclude=.git "$d" | cut -f1))"
      dirs+=("/models/$(dir_of "$m")")
    fi
  done

  echo "[image] $IMAGE"
  docker run --rm --entrypoint python3 --security-opt label=disable \
    -v "$MODELS_DIR":/models:ro -v "$PWD/scripts":/scripts:ro \
    "$IMAGE" /scripts/check_image.py "${dirs[@]}" 2>&1 | grep -E '^ *(OK|FAIL|WARN|\[)' ;;

up)
  m=$(name_of "${2:?give a model name or number (./serve.sh list)}")
  d=$(dir_of "$m"); [[ -n $d ]] || { echo "unknown model: $2 (./serve.sh list)"; exit 1; }
  [[ -d $MODELS_DIR/$d ]] || { echo "model folder not found: $MODELS_DIR/$d"; exit 1; }
  dc rm -sf >/dev/null 2>&1 || true
  docker compose --profile "$m" up -d "$m"
  echo -n "waiting for startup (first run can take 10+ minutes) "
  until curl -fs -m 5 "${VLLM_URL%/v1}/health" >/dev/null; do
    if [[ -z $(running) ]]; then echo; echo "startup failed:"; dc logs --tail 40 "$m"; exit 1; fi
    echo -n .; sleep 10
  done
  echo; echo "ready: $VLLM_URL" ;;

down)
  dc rm -sf ;;

status)
  echo "running: $(running || true)"
  curl -fs -m 5 -H "Authorization: Bearer ${VLLM_API_KEY:-}" "$VLLM_URL/models" | "$PY" -c 'import json,sys; print("models:", [m["id"] for m in json.load(sys.stdin)["data"]])' || echo "no API response"
  nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader ;;

logs)
  dc logs -f --tail 200 "$(running)" ;;

errors)
  dc logs | grep -iE "error|memory|KV cache" || echo "no matching lines" ;;

test)
  "$PY" scripts/test.py ;;

loadtest)
  shift; "$PY" scripts/loadtest.py "$@" ;;

eval)
  shift; "$PY" scripts/eval.py "$@" ;;

test-all)
  out=results/$(date +%Y%m%d-%H%M); mkdir -p "$out"
  for m in $(names); do
    [[ -d $MODELS_DIR/$(dir_of "$m") ]] || continue
    echo "== $m"
    if ./serve.sh up "$m"; then
      { ./serve.sh test; "$PY" scripts/loadtest.py --csv "$out/$m.loadtest.csv"; "$PY" scripts/eval.py; } 2>&1 | tee "$out/$m.txt"
    else
      echo "startup failed" > "$out/$m.txt"
    fi
  done
  ./serve.sh down; echo "results: $out/" ;;

monitor)
  if [[ ${2:-up} == down ]]; then
    docker compose --profile monitoring stop
  else
    docker compose --profile monitoring up -d
    echo "Grafana: http://<server>:${GRAFANA_PORT:-3000} (admin / GRAFANA_ADMIN_PASSWORD)"
  fi ;;

*)
  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
