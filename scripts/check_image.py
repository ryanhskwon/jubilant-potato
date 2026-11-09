#!/usr/bin/env python3
"""Runs inside the vLLM image (serve.sh check): checks the transformers version range and that each model loads."""
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
    print("  OK   vllm {} / transformers {} (required {})".format(vllm, tf, spec))
else:
    print("  FAIL transformers {} is outside the range vllm {} requires ({}) -> pull the image again".format(tf, vllm, spec))

from transformers import AutoConfig, AutoProcessor, AutoTokenizer  # noqa: E402

for path in sys.argv[1:]:
    name = os.path.basename(path)
    try:
        cfg = AutoConfig.from_pretrained(path)
        vision = os.path.exists(os.path.join(path, "preprocessor_config.json"))
        (AutoProcessor if vision else AutoTokenizer).from_pretrained(path)
        print("  OK   {}: {}{}".format(name, cfg.model_type, " (image input)" if vision else ""))
    except Exception as e:  # noqa: BLE001
        print("  FAIL {}: {}".format(name, str(e).splitlines()[0][:160]))
