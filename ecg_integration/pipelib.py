"""공유 유틸: config 로드, 로깅, resumable 헬퍼. (stdlib만 사용)"""
from __future__ import annotations
import json, logging, os, sys
from pathlib import Path

def load_config(path=None):
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    # 경로: ${VAR} 치환 후 FILL_ME 경고. 기본값이 저장소 기준이라 설정 없이도 돈다 (HANDOVER.md §3).
    here = os.path.dirname(os.path.abspath(path))
    repo = os.path.dirname(here)
    subs = {
        "CARDIAC_REPO": os.environ.get("CARDIAC_REPO", repo),
        "CARDIAC_OUT": os.environ.get("CARDIAC_OUT", repo),
        "CARDIAC_DATA": os.environ.get("CARDIAC_DATA", r"D:\data"),
    }
    for k, v in cfg["paths"].items():
        if not isinstance(v, str):
            continue
        for name, val in subs.items():
            v = v.replace("${" + name + "}", val)
        if v.startswith("FILL_ME"):
            logging.warning(f"[config] paths.{k} 미설정: {v}")
        else:
            v = os.path.normpath(v)
        cfg["paths"][k] = v
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
