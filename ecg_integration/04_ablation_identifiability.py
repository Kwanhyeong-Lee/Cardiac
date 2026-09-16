"""Stage 4: 식별성 ablation (echo-only vs echo+ECG).
목표(B3 정면돌파): ECG 추가가 Eed·efficiency·V0·tau 추정의 안정성/식별성을 개선하는가?
지표: 반복 seed에 걸친 예측 분산(↓ 좋음), (모델 연결 시) synthetic recovery RMSE·CI폭.

⚠️ 이 단계는 PINN 학습 모델 연결이 필요. 아래는 대리(proxy) 실험 골격:
   - 회귀 대리모델(예: sklearn)로 두 feature set의 타깃 예측 안정성 비교.
   - 실제 논문 실험은 pinn_hamiltonian_v5의 학습 파이프라인에 두 feature set을 넣어 반복."""
from __future__ import annotations
import json, os
import numpy as np, pandas as pd
from pipelib import load_config, get_logger, ensure_dir

def proxy_stability(df, feats, targets, n_seeds, test_size, lg):
    try:
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import r2_score
    except Exception:
        lg.error("sklearn 없음 → pip install scikit-learn"); return None
    res = {}
    for tgt in targets:
        tcol = tgt if tgt in df.columns else f"pinn_{tgt}" if f"pinn_{tgt}" in df.columns else None
        if tcol is None: lg.warning(f"타깃 {tgt} 컬럼 없음, 스킵"); continue
        use = [c for c in feats if c in df.columns]
        sub = df[use + [tcol]].dropna()
        if len(sub) < 100: lg.warning(f"{tgt}: 유효표본 {len(sub)}<100, 스킵"); continue
        r2s, preds = [], []
        for s in range(n_seeds):
            Xtr, Xte, ytr, yte = train_test_split(sub[use], sub[tcol], test_size=test_size, random_state=s)
            m = GradientBoostingRegressor(random_state=s).fit(Xtr, ytr)
            p = m.predict(Xte); r2s.append(r2_score(yte, p)); preds.append(p.mean())
        res[tgt] = {"n": len(sub), "r2_mean": float(np.mean(r2s)),
                    "pred_std_across_seeds": float(np.std(preds))}
    return res

def main():
    cfg = load_config(); lg = get_logger("ablation", cfg["runtime"]["log_level"])
    out = ensure_dir(cfg["paths"]["out_dir"])
    df = pd.read_csv(os.path.join(out, "cohort_echo_ecg.csv"))
    ab = cfg["ablation"]; report = {}
    for name, feats in ab["feature_sets"].items():
        lg.info(f"--- feature set: {name} ({len(feats)} feats) ---")
        report[name] = proxy_stability(df, feats, ab["targets"], ab["n_seeds"], ab["test_size"], lg)
    # echo_only vs echo_plus_ecg 비교
    comp = {}
    if report.get("echo_only") and report.get("echo_plus_ecg"):
        for tgt in ab["targets"]:
            a = report["echo_only"].get(tgt); b = report["echo_plus_ecg"].get(tgt)
            if a and b:
                comp[tgt] = {"dR2": round(b["r2_mean"]-a["r2_mean"], 4),
                             "dPredStd": round(b["pred_std_across_seeds"]-a["pred_std_across_seeds"], 5)}
    with open(os.path.join(out, "ablation_identifiability.json"), "w", encoding="utf-8") as f:
        json.dump({"per_set": report, "echo_vs_ecg": comp}, f, ensure_ascii=False, indent=2)
    lg.info("비교(ECG 추가 효과): " + json.dumps(comp, ensure_ascii=False))
    lg.info(f"저장 → {os.path.join(out, 'ablation_identifiability.json')}")
    lg.info("주의: 이는 proxy. 논문용은 pinn_hamiltonian_v5 학습에 두 feature set 적용 필요.")

if __name__ == "__main__":
    main()
