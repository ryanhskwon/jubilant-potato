#!/usr/bin/env bash
# vLLM 모델 서빙 (GPU 1장: 한 번에 한 모델)
#
#   ./serve.sh list              모델 목록
#   ./serve.sh check             서버·이미지·모델 점검
#   ./serve.sh up <모델>         모델 실행 (실행 중인 모델은 내림)
#   ./serve.sh down              종료
#   ./serve.sh status            상태
#   ./serve.sh logs              로그
#   ./serve.sh test              기능 점검
#   ./serve.sh loadtest [옵션]   동시 사용자·초당 토큰 측정
#   ./serve.sh eval [옵션]       코딩 과제 평가 (통과율) → results/eval/
#   ./serve.sh test-all          모든 모델 test + loadtest + eval → results/
#   ./serve.sh monitor up|down   Grafana 지표 수집
set -euo pipefail
cd "$(dirname "$0")"
[[ -f .env ]] && { set -a; . ./.env; set +a; }

IMAGE=${VLLM_IMAGE:-vllm/vllm-openai:v0.33.0}
MODELS_DIR=${MODELS_DIR:-/data/models}
export VLLM_URL=http://127.0.0.1:${HOST_PORT:-8000}/v1
PY=$(command -v python3 || echo /usr/libexec/platform-python)

# 모델 이름 (= compose 서비스, configs/<이름>.yaml)   모델 폴더 (MODELS_DIR 아래)
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
dc()      { docker compose --profile all "$@"; }
running() { dc ps --services --status running 2>/dev/null | head -1; }

case ${1:-} in
list)
  for m in $(names); do
    [[ -d $MODELS_DIR/$(dir_of "$m") ]] && s=있음 || s=없음
    printf '%-26s %-34s %s\n' "$m" "$(dir_of "$m")" "$s"
  done ;;

check)
  echo "[GPU]"
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
  drv=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
  (( ${drv%%.*} >= 580 )) || echo "  경고: 드라이버 $drv — vLLM 0.33(CUDA 13)은 R580 이상 필요"

  echo "[모델 폴더]"
  dirs=()
  for m in $(names); do
    d=$MODELS_DIR/$(dir_of "$m")
    if [[ ! -d $d ]]; then echo "  $m: 없음"; continue; fi
    if [[ -n $(find "$d" -maxdepth 1 -name '*.safetensors' -size -2k) ]]; then
      echo "  $m: git-lfs 포인터만 있음 → 폴더에서 git lfs pull"
    else
      echo "  $m: OK ($(du -sh --exclude=.git "$d" | cut -f1))"
      dirs+=("/models/$(dir_of "$m")")
    fi
  done

  echo "[이미지] $IMAGE"
  docker run --rm --entrypoint python3 --security-opt label=disable \
    -v "$MODELS_DIR":/models:ro -v "$PWD/scripts":/scripts:ro \
    "$IMAGE" /scripts/check_image.py "${dirs[@]}" 2>&1 | grep -E '^ *(OK|FAIL|WARN|\[)' ;;

up)
  m=${2:?모델 이름을 지정하세요 (./serve.sh list)}
  d=$(dir_of "$m"); [[ -n $d ]] || { echo "모르는 모델: $m"; exit 1; }
  [[ -d $MODELS_DIR/$d ]] || { echo "모델 폴더 없음: $MODELS_DIR/$d"; exit 1; }
  dc rm -sf >/dev/null 2>&1 || true
  docker compose --profile "$m" up -d "$m"
  echo -n "기동 대기 (첫 실행은 10분 이상 걸릴 수 있음) "
  until curl -fs -m 5 "${VLLM_URL%/v1}/health" >/dev/null; do
    if [[ -z $(running) ]]; then echo; echo "기동 실패:"; dc logs --tail 40 "$m"; exit 1; fi
    echo -n .; sleep 10
  done
  echo; echo "준비 완료: $VLLM_URL" ;;

down)
  dc rm -sf ;;

status)
  echo "실행 중: $(running || true)"
  curl -fs -m 5 -H "Authorization: Bearer ${VLLM_API_KEY:-}" "$VLLM_URL/models" | "$PY" -c 'import json,sys; print("모델:", [m["id"] for m in json.load(sys.stdin)["data"]])' || echo "API 응답 없음"
  nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader ;;

logs)
  dc logs -f --tail 200 "$(running)" ;;

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
      echo "기동 실패" > "$out/$m.txt"
    fi
  done
  ./serve.sh down; echo "결과: $out/" ;;

monitor)
  if [[ ${2:-up} == down ]]; then
    docker compose --profile monitoring stop
  else
    docker compose --profile monitoring up -d
    echo "Grafana: http://<서버>:${GRAFANA_PORT:-3000} (admin / GRAFANA_ADMIN_PASSWORD)"
  fi ;;

*)
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
