"""CFD 모듈 어댑터: windkessel_phpinn_results.json → canonical twin_parameters 레코드.
0D 어댑터(build_twin_parameters.py)와 **동일 스키마**로 append → 통합 버스(0D↔3D) 실증.

정직성 태깅: 현재 CFD는 미수렴(STATUS §18)이라 이 값은 windkessel_phpinn_bridge의
synthetic-validated 산출. 따라서 validation_tier = 'i'(합성/미검증)로 태깅.

실행: python build_twin_parameters_cfd.py
출력: out/twin_parameters_cfd.jsonl (+ 콘솔 요약)
"""
from __future__ import annotations
import argparse, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)

def build_record(d):
    wk = d.get("windkessel", {}); ph = d.get("phpinn", {}); pv = d.get("pv_metrics", {})
    def g(dic, k):
        v = dic.get(k)
        return float(v) if isinstance(v, (int, float)) else None
    return {
        "id": "Case1009_cfd_bridge",
        "provenance": {"modality": "cfd", "source": "Case1009 (windkessel-pHPINN bridge, synthetic-validated; CFD 미수렴)",
                       "subject_id": None, "timestamp": None},
        "hemodynamic": {
            "Ees": g(ph, "Emax"),                 # end-systolic elastance
            "Eed": None,
            "Ea": g(ph, "Ea"),
            "tau": g(ph, "tau_dia"),
            "V0": g(ph, "Vd"),
            "coupling": g(pv, "coupling_ratio_Ea_Emax"),
            "EDP": None,
            "efficiency": g(pv, "mechanical_efficiency"),
        },
        "energetics": {"H_PVA": g(pv, "PVA_mmHg_mL"), "SW": g(pv, "SW_mmHg_mL"),
                       "PE": g(pv, "PE_mmHg_mL"), "eff": g(pv, "mechanical_efficiency")},
        "windkessel": {"R1": g(wk, "R1"), "R2": g(wk, "R2"), "C": g(wk, "C")},
        "geometry": {"mesh_ids": ["lv_surface.stl"], "LV_mL": None, "RV_mL": None},
        "ep": {"QRS_ms": None, "QTc_ms": None, "LVH_mV": None, "PTFV1": None, "AF": None},
        "validation_tier": {"Ees": "i", "Ea": "i", "tau": "i", "V0": "i",
                            "coupling": "i", "efficiency": "i"},
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=os.path.join(PROJ, "windkessel_phpinn_results.json"))
    ap.add_argument("--out_dir", default=os.path.join(HERE, "out"))
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    d = json.load(open(a.input, encoding="utf-8"))
    rec = build_record(d)
    outf = os.path.join(a.out_dir, "twin_parameters_cfd.jsonl")
    with open(outf, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    print(f"\n[OK] CFD record → {outf}")
    print("→ 0D 어댑터와 동일 스키마. 통합 저장소는 두 jsonl을 concat하면 됨(id로 구분).")

if __name__ == "__main__":
    main()
