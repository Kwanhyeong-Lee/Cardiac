"""Stage 0: 환경·경로·입력 점검. 데이터 pull 전에도 실행 가능(경로만 확인)."""
from __future__ import annotations
import importlib, os, sys
from pipelib import load_config, get_logger

REQUIRED = ["pandas", "numpy", "scipy"]
OPTIONAL = ["wfdb", "neurokit2", "torch", "sklearn", "matplotlib"]

def main():
    cfg = load_config()
    lg = get_logger("env", cfg["runtime"]["log_level"])
    lg.info(f"python {sys.version.split()[0]}")

    ok = True
    for m in REQUIRED:
        try: importlib.import_module(m); lg.info(f"[req] {m} OK")
        except Exception as e: ok = False; lg.error(f"[req] {m} 없음 → pip install {m}")
    for m in OPTIONAL:
        try: importlib.import_module(m); lg.info(f"[opt] {m} OK")
        except Exception: lg.warning(f"[opt] {m} 없음(파형/모델 단계에서 필요할 수 있음)")

    lg.info("--- 경로 점검 ---")
    p = cfg["paths"]
    for k in ["echo_cohort_csv", "pinn_cohort_csv"]:
        lg.info(f"{k}: {'OK' if os.path.exists(p[k]) else '없음'} ({p[k]})")
    ecg = p["ecg_root"]
    if ecg.startswith("FILL_ME"):
        lg.warning("ecg_root 미설정 → PhysioNet에서 MIMIC-IV-ECG pull 후 config.json 채우기(RUNBOOK 참조)")
    else:
        for f in ["record_list.csv", "machine_measurements.csv"]:
            fp = os.path.join(ecg, f)
            lg.info(f"ecg/{f}: {'OK' if os.path.exists(fp) else '없음'}")
    lg.info("환경점검 완료" + ("" if ok else " (필수 패키지 누락 있음!)"))
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
