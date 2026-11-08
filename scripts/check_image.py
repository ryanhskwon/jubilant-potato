#!/usr/bin/env python3
"""vLLM 이미지 안에서 실행 (serve.sh check): transformers 버전 범위와 모델별 로드 확인."""
import importlib.metadata as md
import os
import sys
import warnings

from packaging.requirements import Requirement
from packaging.version import Version

warnings.filterwarnings("ignore")
os.environ["HF_HUB_OFFLINE"] = "1"

tf = md.version("transformers")
vllm = md.version("vllm")
spec = next((Requirement(r).specifier for r in md.requires("vllm") or [] if Requirement(r).name == "transformers"), None)
if spec is None or spec.contains(Version(tf), prereleases=True):
    print("  OK   vllm {} / transformers {} (요구 범위 {})".format(vllm, tf, spec))
else:
    print("  FAIL transformers {}가 vllm {}의 요구 범위 {} 밖 → 이미지를 다시 받으세요".format(tf, vllm, spec))

from transformers import AutoConfig, AutoProcessor, AutoTokenizer  # noqa: E402

for path in sys.argv[1:]:
    name = os.path.basename(path)
    try:
        cfg = AutoConfig.from_pretrained(path)
        vision = os.path.exists(os.path.join(path, "preprocessor_config.json"))
        (AutoProcessor if vision else AutoTokenizer).from_pretrained(path)
        print("  OK   {}: {}{}".format(name, cfg.model_type, " (이미지 입력)" if vision else ""))
    except Exception as e:  # noqa: BLE001
        print("  FAIL {}: {}".format(name, str(e).splitlines()[0][:160]))
