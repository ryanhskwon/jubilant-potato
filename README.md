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
| `qwen3.6-35b-a3b-fp8` | `qwen3.6-35b-a3b-fp8` | 262K | MoE, 사고, 이미지, MTP |
| `gemma-4-31b-it-fp8` | `gemma-4-31b-it-fp8` | 128K | 사고, 이미지 |
| `qwen3-coder-30b-a3b-fp8` | `qwen3-coder-30b-a3b` | 262K | MoE, 코딩 전용 |
| `qwen3-coder-next-fp8` | `qwen3-coder-next` | 128K | 80B MoE, 코딩 전용 |

모델별 옵션은 `configs/<이름>.yaml`에 있습니다.

## 부하 테스트

```bash
./serve.sh loadtest --users 1,4,8,16 --input 8000 --output 512 --ttft 3 --tps 20 --csv result.csv
```

동시 사용자를 늘려 가며 아래 지표를 잽니다.
- 첫 토큰까지 시간 (p50/p95)
- 사용자당 출력 속도
- 전체 초당 토큰

목표를 지키는 최대 동시 사용자 수도 함께 알려 줍니다. 기본 목표는 첫 토큰 p95 5초 이하, 사용자당 15 tok/s 이상입니다.

- **동시 처리 한도:** yaml의 `max-num-seqs`(기본 8)를 넘는 요청은 대기합니다. 한계를 재려면 32~64로 올리고 다시 측정하세요.
- **"동시 사용자"의 의미:** 같은 순간 요청 중인 수입니다. 실제 사용자는 쉬는 시간이 있으므로, 사용 비율이 20%라면 동시 8은 약 40명입니다. 실제 비율은 Grafana로 확인하세요.

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
