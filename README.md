# jubilant-potato

vLLM 0.33으로 6개 모델을 서빙합니다. 대상 서버는 Rocky Linux + RTX PRO 6000 1장이라 한 번에 한 모델만 띄웁니다. HTML 가이드: [docs/guide.html](docs/guide.html) · 복붙용 명령어: [COMMANDS.txt](COMMANDS.txt)

## 준비

- NVIDIA 드라이버 R580 이상 (vLLM 0.33 이미지는 CUDA 13 전용)
- Docker, docker compose, nvidia-container-toolkit
- 모델은 `/data/models` 아래에 `git lfs install` 후 git clone

```bash
cp .env.example .env      # 외부에 열면 VLLM_API_KEY 설정
./serve.sh check          # 드라이버, 이미지(transformers 버전 포함), 모델 폴더 점검
```

## 사용

```bash
./serve.sh up qwen3.8-27b-nvfp4   # 실행 (실행 중인 모델은 자동으로 내림)
./serve.sh test                   # 텍스트, 도구 호출, 이미지, 속도
./serve.sh loadtest               # 동시 사용자 수별 응답 속도와 초당 토큰
./serve.sh eval                   # 코딩 과제 평가 (통과율)
./serve.sh status | logs | down
./serve.sh test-all               # 모든 모델 test + loadtest + eval → results/
./serve.sh monitor up             # Grafana(:3000)로 상시 지표 수집
```

클라이언트(OpenAI 호환)는 `http://<서버>:8000/v1`에 연결하고, API 키는 `.env`의 `VLLM_API_KEY`를 씁니다.

## 모델

| 이름 | API 모델 이름 | 컨텍스트 | 특징 |
|---|---|---|---|
| `qwen3.8-27b-fp8` | `qwen3.8-27b-fp8` | 262K | 사고, 이미지, MTP |
| `qwen3.8-27b-nvfp4` | `qwen3.8-27b-nvfp4` | 262K | 사고, 이미지, MTP |
| `qwen3.6-35b-a3b-fp8` | `qwen3.6-35b-a3b-fp8` | 262K | MoE, 사고, 이미지 (MTP 끔: 0.33에서 기동 오류) |
| `gemma-4-26b-a4b-it` | `gemma-4-26b-a4b-it` | 128K | MoE (활성 약 4B), 사고, 이미지 |
| `qwen3-coder-30b-a3b-fp8` | `qwen3-coder-30b-a3b` | 262K | MoE, 코딩 전용 |
| `qwen3-coder-next-fp8` | `qwen3-coder-next` | 128K | 80B MoE, 코딩 전용 |
| `gemma-4-31b-it-fp8` | `gemma-4-31b-it-fp8` | 128K | 사고, 이미지 (긴 입력 처리가 느려 26B로 교체, 기록용) |

모델별 옵션은 `configs/<이름>.yaml`에 있습니다.

## 부하 테스트

```bash
./serve.sh loadtest                              # 기본: 단계마다 180초, 최대 약 35분
./serve.sh loadtest --users 1,2 --duration 30    # 빠른 확인
./serve.sh loadtest --users 1,2,4,8,12,16        # 목표 개발자 15명: 16에서 OK인지
./serve.sh loadtest --natural --users 1,4        # 실제 대기 시간 (모델이 스스로 멈춤)
./serve.sh loadtest --context 30000 --turns 10   # 더 큰 코드, 더 긴 세션
```

취약점 점검 + 수정 에이전트의 작업 모양으로 부하를 겁니다.
- **세션:** 가상 사용자마다 자기 코드(서버의 Python 설치에 있는 실제 `.py` 파일, 약 `--context` 2만 토큰)로 점검을 시작하고 `--turns`(8)번 모델을 호출합니다. 호출마다 모델 답과 도구 결과(코드 약 1000토큰)가 붙어 컨텍스트가 커지고, prefix cache는 같은 세션 안에서만 재사용됩니다.
- **단계:** 동시 세션을 `--users`(1, 2, 4, 8, 12, 16, 24, 32, 48, 64) 순서로 늘리고, 단계마다 `--duration`(180)초 동안 측정합니다. 두 단계 연속 목표 미달이면 멈춥니다.
- **지표:** TTFT p50/p95, 호출당 출력 tok/s (p50, p5), 지연 p95, 전체 출력 tok/s, 서버의 KV 캐시 사용률과 대기 요청. `limit` 칸이 한계 원인을 보여 줍니다 (`KV` 캐시 부족, `seqs` max-num-seqs 대기, `pref` 새 세션의 prefill 대기, `gpu` 연산).
- **서버 분석 표:** vLLM `/metrics`에서 호출당 평균 queue(대기열) / prefill / decode 시간, prefix cache 적중률, prefill tok/s(캐시 제외 입력 처리 속도), 최대 running / waiting을 단계별로 보여 줍니다. TTFT는 대략 queue + prefill이라, TTFT가 늦은 이유가 대기인지 입력 처리인지 구분됩니다.
- **목표:** TTFT p95 5초 이하, 호출의 95%가 20 tok/s 이상 (`--ttft`, `--tps`로 변경).
- **결론:** 목표를 지키는 최대 동시 세션, 그 부하에서의 속도와 세션 1건 소요 시간, 배치 최대 처리량(시간당 세션), 사용 비율 5/10/25/50%별 등록 사용자 수, 운영용 `max-num-seqs` 권장값. 낮에 배치 작업이 세션을 차지한다면 `--batch-sessions N`으로 빼고 계산합니다.
- **저장:** `results/loadtest/<모델>-<날짜>.txt`와 `.csv`.

참고할 점.
- **max-num-seqs:** 측정을 위해 64로 올려 두었습니다 (`qwen3-coder-next`는 메모리가 빠듯해 4 유지). 측정 후 운영에서는 결과의 권장값으로 낮추세요. 넘치는 요청은 대기열에 서서 다른 사용자 속도를 떨어뜨리지 않습니다.
- **최악 조건:** 호출 사이 쉬는 시간이 없다고 가정합니다. 실제 에이전트는 테스트 실행 등으로 쉬는 시간이 있어 조금 더 많은 사용자를 받을 수 있습니다.
- **목표 개발자 10~15명:** 16 동시 세션이 `OK`면 전원이 동시에 점검해도 목표 속도가 지켜집니다. 이 규모에서는 동시 사용자 수보다 점검 1건 대기 시간이 더 중요합니다.
- **`--natural`:** 기본 모드는 비교를 위해 호출마다 출력을 512토큰으로 고정합니다. 사고(thinking) 모델은 실제로 더 길게 생각할 수 있어서, 이 옵션으로 모델이 스스로 멈추게 두고(최대 4096토큰) 실제 점검 1건 시간과 호출당 출력 토큰(사고 포함)을 확인합니다. 출력 길이가 모델마다 달라서 모델 간 용량 비교에는 기본 모드를 쓰세요.
- **MTP:** Qwen3.8 설정 두 개는 speculative decoding(MTP)을 켜 두었고 (qwen3.6은 기동 오류로 꺼 둠), 속도 이득은 코드 내용에 따라 달라집니다. 그래서 합성 텍스트가 아닌 실제 코드를 씁니다.

## 모델 선택 평가

품질은 `eval`, 속도는 `loadtest`로 잽니다. 모델을 하나씩 띄워 두 가지를 모두 실행한 뒤 비교합니다.

```bash
./serve.sh up qwen3.8-27b-nvfp4 && ./serve.sh eval   # 모델마다 반복 (또는 ./serve.sh test-all)
```

- **평가 방식:** 모델이 도구(파일 목록·읽기·쓰기·테스트 실행)로 `evals/tasks/`의 과제를 풀고, 테스트 통과 여부로 채점합니다.
- **결과:** 실행할 때마다 `results/eval/summary.csv`에 모델별 한 줄이 쌓이고, 통과율 순 비교표가 출력됩니다.
- **과제 추가:** `evals/tasks/<이름>/`에 다음 세 가지를 넣습니다. 샘플 4개가 들어 있지만, 실제 업무 과제 20~50개로 바꿔야 의미 있는 비교가 됩니다.
  - `task.md`: 지시문
  - `files/`: 시작 코드
  - `tests/test_*.py`: 채점용 unittest
- **선택 기준:** 품질 기준(예: 통과율 70%)을 넘는 모델 중에서, `loadtest`의 최대 동시 사용자가 가장 많은 모델을 고릅니다.
- **주의:** 모델이 작성한 코드가 서버의 임시 폴더에서 실행됩니다 (테스트당 60초 제한).

## 문제 해결

OOM 단계별 대처와 증상별 조치는 [docs/guide.html](docs/guide.html#troubleshooting)의 트러블슈팅에 정리했습니다. 자주 쓰는 것:

| 증상 | 조치 |
|---|---|
| check: transformers 범위 밖 | 공식 이미지를 다시 받기 (`docker pull vllm/vllm-openai:v0.33.0`). 컨테이너 안에서 transformers를 올리지 말 것 |
| check: git-lfs 포인터 | 모델 폴더에서 `git lfs pull` |
| Qwen 기동 실패 | yaml의 `speculative-config` 줄 삭제 (MTP 설정이 0.33에서 미검증) |
| Gemma 도구 호출이 텍스트로 나옴 | yaml의 `reasoning-parser` 줄 삭제 ([vllm#39468](https://github.com/vllm-project/vllm/issues/39468)) |
| 메모리 부족 (OOM) | `max-model-len` 절반 → `gpu-memory-utilization: 0.95` → `speculative-config` 삭제 → `enforce-eager: true` 순서로 시도 |

## 참고

- vLLM 레시피
  - [Qwen3.8-27B](https://recipes.vllm.ai/Qwen/Qwen3.8-27B)
  - [Qwen3.6-35B-A3B](https://recipes.vllm.ai/Qwen/Qwen3.6-35B-A3B)
  - [Gemma 4](https://recipes.vllm.ai/Google/gemma-4-31B-it)
- [vLLM 릴리스 노트](https://github.com/vllm-project/vllm/releases)
- 각 모델의 Hugging Face 카드
