"""공유 유틸: config 로드, 로깅, resumable 헬퍼. (stdlib만 사용)"""
from __future__ import annotations
import json, logging, os, sys
from pathlib import Path

def load_config(path=None):
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    # 경로 검증(FILL_ME 남아있으면 경고)
    for k, v in cfg["paths"].items():
        if isinstance(v, str) and v.startswith("FILL_ME"):
            logging.warning(f"[config] paths.{k} 미설정: {v}")
    return cfg

def get_logger(name, level="INFO"):
    lg = logging.getLogger(name)
    if not lg.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                                         "%H:%M:%S"))
        lg.addHandler(h)
    lg.setLevel(getattr(logging, level, logging.INFO))
    return lg

def ensure_dir(p):
    Path(p).mkdir(parents=True, exist_ok=True)
    return p

def done_marker(out_dir, stage):
    return os.path.join(out_dir, f".{stage}.done")

def is_done(out_dir, stage, resume=True):
    return resume and os.path.exists(done_marker(out_dir, stage))

def mark_done(out_dir, stage):
    with open(done_marker(out_dir, stage), "w") as f:
        f.write("ok")

def first_present(cols, candidates):
    for c in candidates:
        if c in cols:
            return c
    return None
