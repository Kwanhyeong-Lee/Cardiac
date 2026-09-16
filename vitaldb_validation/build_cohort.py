"""VitalDB 코호트 구축: ART 파형 + CO + SV (+CVP) 케이스의 대표값 수집."""
import pandas as pd, numpy as np, vitaldb, os
HERE=os.path.dirname(os.path.abspath(__file__))
tr=pd.read_csv('https://api.vitaldb.net/trks'); S=lambda t:set(tr.loc[tr.tname==t,'caseid'])
ids=sorted(S('SNUADC/ART') & (S('EV1000/CO')|S('Vigileo/CO')) & (S('EV1000/SV')|S('Vigileo/SV')))
print("cohort candidates:",len(ids))
rows=[]
for k,cid in enumerate(ids):
    try:
        v=vitaldb.load_case(cid,['EV1000/CO','EV1000/SV','EV1000/CVP',
                                 'Vigileo/CO','Vigileo/SV','Solar8000/CVP'],1)
        if v is None or v.size==0: continue
        f=lambda j: float(np.nanmedian(v[:,j])) if np.isfinite(v[:,j]).any() else np.nan
        CO=f(0) if np.isfinite(f(0)) else f(3); SV=f(1) if np.isfinite(f(1)) else f(4)
        CVP=f(2) if np.isfinite(f(2)) else (f(5) if np.isfinite(f(5)) else 0.0)
        if np.isfinite(CO) and np.isfinite(SV): rows.append(dict(caseid=cid,CO=CO,SV=SV,CVP=CVP))
    except Exception: pass
    if k%50==0: print(f"  {k}/{len(ids)} -> {len(rows)} ok")
pd.DataFrame(rows).to_csv(os.path.join(HERE,"cohort.csv"),index=False)
print("saved cohort.csv:",len(rows))
