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
./serve.sh test-all 1 3 4         # 고른 모델 test + 취약점 eval 일부 + 긴 코딩 과제 → results/, 끝나면 report
./serve.sh report                 # results/ 를 읽어 가장 알맞은 모델 추천
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
- **세션:** 가상 사용자마다 자기 코드(서버의 Python 설치에 있는 실제 `.py` 파일, 약 `--context` 2만 토큰)로 점검을 시작하고 `--turns`(8)번 모델을 호출합니다. 호출마다 모델 답과 도구 결과(코드 약 1000토큰)가 붙어 컨텍스트가 커지고, prefix cache는 같은 세션 안에서만 재사용됩니다. 파일은 고정된 순서(seed)로 골라서 모든 모델이 같은 코드를 받습니다. 문자표(`encodings/`), 테스트, 이스케이프가 많은 파일은 토큰이 촘촘해서 뺍니다. 같은 코드라도 토크나이저에 따라 토큰 수가 다르므로, 결과의 `tokens per call`이 목표와 20% 넘게 다르면 경고가 나옵니다.
- **단계:** 동시 세션을 `--users`(1, 2, 4, 6, 8, 12, 16) 순서로 늘리고, 단계마다 `--duration`(180)초 동안 측정합니다. 두 단계 연속 목표 미달이면 멈춥니다.
- **지표:** TTFT p50/p95, 호출당 출력 tok/s (p50, p5), 지연 p95, 전체 출력 tok/s, 서버의 KV 캐시 사용률과 대기 요청. `limit` 칸이 한계 원인을 보여 줍니다 (`KV` 캐시 부족, `seqs` max-num-seqs 대기, `pref` 새 세션의 prefill 대기, `gpu` 연산).
- **서버 분석 표:** vLLM `/metrics`에서 호출당 평균 queue(대기열) / prefill / decode 시간, prefix cache 적중률, prefill tok/s(캐시 제외 입력 처리 속도), 최대 running / waiting을 단계별로 보여 줍니다. TTFT는 대략 queue + prefill이라, TTFT가 늦은 이유가 대기인지 입력 처리인지 구분됩니다.
- **목표:** TTFT p95 5초 이하, 호출의 95%가 20 tok/s 이상 (`--ttft`, `--tps`로 변경).
- **결론:** 목표를 지키는 최대 동시 세션, 그 부하에서의 속도와 세션 1건 소요 시간, 배치 최대 처리량(시간당 세션), 사용 비율 5/10/25/50%별 등록 사용자 수, 운영용 `max-num-seqs` 권장값. 낮에 배치 작업이 세션을 차지한다면 `--batch-sessions N`으로 빼고 계산합니다.
- **저장:** `results/loadtest/<모델>-<날짜>.txt`와 `.csv`.

참고할 점.
- **max-num-seqs:** 모든 모델 16입니다. 1차 측정에서 속도 목표를 지킨 최대치가 15세션이었고, 목표 인원이 10~15명이기 때문입니다. 16을 넘는 요청은 대기열에 서므로 다른 사용자의 생성 속도를 떨어뜨리지 않고, 대기 시간은 TTFT에 잡힙니다.
- **최악 조건:** 호출 사이 쉬는 시간이 없다고 가정합니다. 실제 에이전트는 테스트 실행 등으로 쉬는 시간이 있어 조금 더 많은 사용자를 받을 수 있습니다.
- **목표 개발자 10~15명:** 16 동시 세션이 `OK`면 전원이 동시에 점검해도 목표 속도가 지켜집니다. 이 규모에서는 동시 사용자 수보다 점검 1건 대기 시간이 더 중요합니다.
- **`--natural`:** 기본 모드는 비교를 위해 호출마다 출력을 512토큰으로 고정합니다. 사고(thinking) 모델은 실제로 더 길게 생각할 수 있어서, 이 옵션으로 모델이 스스로 멈추게 두고(최대 4096토큰) 실제 점검 1건 시간과 호출당 출력 토큰(사고 포함)을 확인합니다. 출력 길이가 모델마다 달라서 모델 간 용량 비교에는 기본 모드를 쓰세요.
- **MTP:** Qwen3.8 설정 두 개는 speculative decoding(MTP)을 켜 두었고 (qwen3.6은 기동 오류로 꺼 둠), 속도 이득은 코드 내용에 따라 달라집니다. 그래서 합성 텍스트가 아닌 실제 코드를 씁니다.

## 모델 선택 평가

품질은 `eval`, 속도는 `loadtest`로 잽니다. 모델을 하나씩 띄워 두 가지를 모두 실행한 뒤 비교합니다.

```bash
./serve.sh up qwen3.8-27b-nvfp4 && ./serve.sh eval   # 모델마다 반복 (또는 ./serve.sh test-all)
```

- **평가 방식:** 모델이 도구(파일 목록·읽기·쓰기·테스트 실행)로 `evals/tasks/`의 과제를 풀고, 테스트 통과 여부로 채점합니다. 모델 호출당 최대 출력은 16,384토큰으로, 회사 코딩 에이전트(gemma-4-31b)와 같은 값입니다.
- **결과:** 실행할 때마다 `results/eval/summary.csv`에 모델별 한 줄이 쌓이고, 통과율 순 비교표가 출력됩니다.
- **과제 추가:** `evals/tasks/<이름>/`에 다음 세 가지를 넣습니다. 샘플 4개가 들어 있지만, 실제 업무 과제 20~50개로 바꿔야 의미 있는 비교가 됩니다.
  - `task.md`: 지시문
  - `files/`: 시작 코드
  - `tests/test_*.py`: 채점용 unittest
- **선택 기준:** 품질 기준(예: 통과율 70%)을 넘는 모델 중에서, `loadtest`의 최대 동시 사용자가 가장 많은 모델을 고릅니다.

### 모델 고르기: 현장 방문 흐름 (`test-all`, `report`)

```bash
git pull
python3 scripts/check_tasks.py evals/vuln evals/long   # 22 of 22 tasks ok 가 나와야 함
./serve.sh test-all 1 3 4                   # 번호나 이름으로 모델 선택 (생략하면 폴더가 있는 모든 모델)
./serve.sh report                           # 표 + "recommended: <모델>"
LONG=0 ./serve.sh test-all 1 3 4            # 시간이 없을 때: 긴 코딩 과제 빼기
VULN_TASKS=all ./serve.sh test-all 1 3 4    # 느린 경로: 21개 과제 전체
```

- **모델마다 하는 일:** 기동, `test`(텍스트·도구·이미지·속도), 취약점 eval 6개 과제(`VULN_TASKS`로 바꿈, `all` 또는 빈 값이면 21개 전체), 긴 코딩 과제 1개(`LONG=0`이면 건너뜀). `loadtest`는 돌리지 않습니다. 끝나면 모델을 내리고 `report`를 실행합니다.
- **시간(추정치, 실측 아님):** 모델당 약 25~30분. 모델 기동, 6개 과제 평가, 긴 코딩 과제(최대 9분)입니다. 긴 과제를 빼면 약 15~20분입니다. 21개 전체와 첫 기동(캐시 없음)은 더 걸립니다.
- **입력:** `results/test/<모델>.json`(도구 호출 통과 여부), `results/eval/summary-vuln.csv`(모델별 최신 줄), `results/loadtest/<모델>-*.csv`(가장 최근 파일). 동시 사용자 수는 이전에 `./serve.sh loadtest`로 잰 결과를 그대로 씁니다. 없는 모델은 `-`로 표시하고 `missing:`에 올리며, 품질만으로 순위를 매깁니다.
- **탈락 조건:** 도구 호출 점검 실패, 또는 loadtest가 있고 목표 속도를 지키는 최대 동시 사용자가 4명 미만(개발자 15명의 예상 동시 접속). 탈락 사유는 `excluded:`에 나옵니다.
- **순위:** 취약점 eval 통과율 내림차순. 통과율 차이가 1개 과제 이내(과제 21개면 약 4.8점, 빠른 세트 6개면 약 16.7점)이면 동률로 보고 최대 동시 사용자, 그다음 세션 1건 시간(`session_s`, 짧은 쪽)으로 정합니다. 실행마다 결과가 흔들리기 때문입니다.
- **주의:** 표의 `pass` 칸은 통과율과 과제 수(예: `3/5`)를 함께 보여 줍니다. 6개 과제만 돌린 결과는 작은 표본이라 차이가 작으면 해석에 주의하세요.
- **`long` 칸:** 긴 코딩 과제 점수(0~100)입니다. 과제가 하나뿐이라 한 번의 실행으로 흔들리기 쉬워 순위에는 쓰지 않고 함께 보여 줍니다.
- **저장:** `results/report.csv`.

### 취약점 점검·수정 평가 (`evals/vuln/`)

```bash
./serve.sh eval --tasks evals/vuln                        # 21개 과제
./serve.sh eval --tasks evals/vuln --only sql-injection,xss
python3 scripts/check_tasks.py evals/vuln                 # 모델 없이 과제 채점 검증
```

취약한 Python 코드 18개와 취약점이 없는 정상 코드 3개입니다. 모든 과제에 같은 지시문("취약점을 찾아 고치고 FINDINGS.json에 CWE를 적어라")을 주므로, 모델은 어떤 취약점인지, 취약점이 있기는 한지 모르고 시작합니다.

| 과제 | CWE |
|---|---|
| sql-injection, command-injection, eval-injection, unsafe-pickle | 89, 78, 95, 502 |
| path-traversal, zip-slip, ssrf, open-redirect | 22, 22, 918, 601 |
| xss, log-injection, mass-assignment, idor | 79, 117, 915, 639 |
| weak-password-hash, hardcoded-secret, insecure-random, timing-compare | 916, 798, 330, 208 |
| redos, temp-file | 1333, 377 |
| clean-sales-report, clean-user-lookup, clean-version | 없음 (오탐 측정) |

- **채점:** `tests/test_func_*.py`는 기능이 그대로인지, `tests/test_sec_*.py`는 공격 입력이 막히는지 봅니다. 모델의 run_tests 도구는 기능 테스트만 실행하고, 공격 테스트는 채점 때만 실행합니다.
- **지표:** 탐지율(보고한 CWE가 정답 목록과 맞고, 한 과제에 서로 다른 CWE를 3개 이하로 보고), 수정률(기능 테스트와 공격 테스트를 모두 통과), 회귀(기능 테스트 실패), 오탐(정상 코드에 취약점 보고). 통과 = 탐지 + 수정. 정상 코드는 FINDINGS.json을 내고 비어 있으며 기능이 그대로여야 통과합니다.
- **결과:** `results/eval/summary-vuln.csv`에 모델별 한 줄이 쌓입니다. 비교표와 `report`는 같은 과제 목록으로 돌린 결과끼리만 비교합니다 (빠른 세트 6개와 전체 21개를 섞지 않음).
- **과제 구조:** `task.md`, `files/`(취약한 코드), `tests/`, `expected.json`(정답 CWE 목록, 정상 코드는 `[]`), `solution/`(모범 수정본, 검증용이며 모델에게 보이지 않음), `alternatives/`(다른 방식의 수정. `good-*`는 맞는 수정이라 통과해야 하고 `bad-*`는 틀리거나 불완전한 수정이라 떨어져야 함. `check_tasks.py`가 확인).
- **주의:** 모델이 작성한 코드가 서버의 임시 폴더에서 실행됩니다 (테스트당 60초 제한).

### 긴 코딩 과제 (`evals/long/`)

```bash
./serve.sh eval --tasks evals/long --max-turns 40 --time-limit 540   # 9분 제한
python3 scripts/check_tasks.py evals/long
```

여러 파일을 읽고, 여러 모듈을 함께 고치는 능력을 봅니다. 과제는 `ticket-tracker` 하나입니다. 모듈 6개짜리 작은 티켓 관리 프로그램에 실제 업무처럼 변경 요청서를 줍니다.

- **요청 내용:** 버그 1개(티켓을 지우면 다음 티켓이 번호를 재사용해 기존 티켓을 덮어씀), 담당자와 마감일 기능, 데이터 파일 형식 버전 2(예전 버전 1 파일도 읽고, 더 새 버전은 거부), 명령줄 옵션 4개, 보고서 항목 2개. 정답 기준으로 5개 파일을 고쳐야 합니다.
- **채점:** 모델의 run_tests 도구는 보이는 테스트 11개(`test_func_*`, 기존 기능과 요청 일부)만 실행합니다. 숨은 인수 테스트 16개(`test_accept_*`)는 끝난 뒤에만 돌려, 요청서를 끝까지 지켰는지 봅니다. 숨은 테스트는 요청서에 적힌 이름과 형식만 검사합니다.
- **시간 제한:** `test-all`은 9분(`--time-limit 540`)이 지나면 모델을 멈추고, 그때까지 고친 코드로 채점합니다. 그래서 점수는 "9분 안에 요청서의 몇 %를 해냈나"이며, 느린 모델은 그만큼 불리합니다. 실제 업무에서도 기다리는 시간이 비용이라 의도한 것입니다. 제한에 걸리면 결과 줄 끝에 `time limit`이 찍힙니다.
- **점수(0~100):** 시작 코드에서 실패하던 테스트 가운데 모델 작업 뒤 통과한 비율입니다. 원래 통과하던 테스트를 망가뜨리면 점수가 깎입니다. 모든 테스트를 통과하면 100이고, 아무것도 안 하면 0입니다. 요청 하나를 빠뜨린 구현(`alternatives/bad-*`)은 94점입니다.
- **결과:** `results/eval/summary-long.csv`. `report` 표의 `long` 칸에 나옵니다.

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
