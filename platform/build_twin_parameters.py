"""플랫폼 backbone 어댑터: PINN 출력 CSV → canonical twin_parameters 레코드(JSONL).
표준 라이브러리(csv/json)만 사용 — pandas 등 설치 불필요.

실행: python build_twin_parameters.py [--input CSV] [--out_dir DIR]
기본 입력: ../mimic_pinn_v4_inference.csv
출력: out/twin_parameters_0d.jsonl + out/twin_parameters_summary.json
"""
from __future__ import annotations
import argparse, csv, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)

# CSV 컬럼 → 스키마 hemodynamic 필드
HEMO_MAP = {"Ees": "pinn_Ees", "Eed": "pinn_Eed", "Ea": "pinn_Ea",
            "coupling": "pinn_coupling", "EDP": "pinn_EDP",
            "efficiency": "pinn_efficiency", "tau": "pinn_tau", "V0": "latent_V0"}
# 검증 tier: Ees는 침습(동물) 검증 존재(ii), 나머지는 합성 recovery(i)
TIER = {"Ees": "ii", "Eed": "i", "Ea": "i", "coupling": "i",
        "EDP": "i", "efficiency": "i", "tau": "i", "V0": "i"}

def num(v):
    """CSV 문자열 → float 또는 None(빈값/파싱실패/NaN)."""
    if v is None or v == "":
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None

def build_record(row):
    hemo = {k: num(row.get(src)) for k, src in HEMO_MAP.items()}
    mid = (row.get("measurement_id") or "").strip()
    sid = (row.get("subject_id") or "").strip()
    sid_num = num(sid)
    return {
        "id": mid if mid else sid,
        "provenance": {"modality": "echo", "source": "MIMIC-IV",
                       "subject_id": int(sid_num) if sid_num is not None else None,
                       "timestamp": (row.get("measurement_datetime") or None)},
        "hemodynamic": hemo,
        "energetics": {"H_PVA": None, "SW": None, "PE": None, "eff": None},
        "windkessel": {"R1": None, "R2": None, "C": None},
        "geometry": {"mesh_ids": [], "LV_mL": None, "RV_mL": None},
        "ep": {"QRS_ms": None, "QTc_ms": None, "LVH_mV": None, "PTFV1": None, "AF": None},
        "validation_tier": dict(TIER),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=os.path.join(PROJ, "mimic_pinn_v4_inference.csv"))
    ap.add_argument("--out_dir", default=os.path.join(HERE, "out"))
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    jsonl = os.path.join(a.out_dir, "twin_parameters_0d.jsonl")

    n = 0
    nonnull = {k: 0 for k in HEMO_MAP}
    with open(a.input, newline="", encoding="utf-8") as fin, \
         open(jsonl, "w", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        for row in reader:
            rec = build_record(row)
            for k in HEMO_MAP:
                if rec["hemodynamic"][k] is not None:
                    nonnull[k] += 1
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1

    summary = {
        "input": os.path.basename(a.input), "n_records": n,
        "modality": "echo", "source": "MIMIC-IV",
        "hemo_nonnull_pct": {k: (round(nonnull[k] / n * 100, 1) if n else 0.0) for k in HEMO_MAP},
        "validation_tier_legend": {"i": "합성recovery", "ii": "침습(동물)", "iii": "임상outcome"},
        "tier_assigned": TIER,
        "output_jsonl": jsonl,
        "note": "energetics/windkessel/geometry/ep는 해당 모듈(CFD/ECG) append 대기",
    }
    with open(os.path.join(a.out_dir, "twin_parameters_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n[OK] {n} records → {jsonl}")

if __name__ == "__main__":
    main()
