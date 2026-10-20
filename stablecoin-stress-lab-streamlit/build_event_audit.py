"""Post-hoc chronological event audit; no claim of preregistration or structural ABM validation."""
import json,hashlib
from datetime import date,timedelta,datetime,timezone
from pathlib import Path
import numpy as np
from backend.app.data_sources.prices import load_prices
from econometrics import evaluate_intervals,MODELS
ROOT=Path(__file__).resolve().parent
CASES=[('USDT · Terra May 2022','USDT','2022-05-08','2022-05-16'),('USDT · FTX Nov 2022','USDT','2022-11-06','2022-11-15'),('USDC · SVB Mar 2023','USDC','2023-03-09','2023-03-15')]

def build():
    source=load_prices();out=[]
    for name,asset,start,end in CASES:
        warm=(date.fromisoformat(start)-timedelta(days=120)).isoformat()
        items=sorted((r['date_utc'],float(r['close_usd'])) for r in source if r['asset']==asset and warm<=r['date_utc']<=end)
        if any((date.fromisoformat(b[0])-date.fromisoformat(a[0])).days!=1 for a,b in zip(items,items[1:])):raise ValueError('Daily gap')
        result=evaluate_intervals(items,1,'Bounded ACI')
        predictions=[r for r in result['predictions'] if start<=r['target']<=end]
        rows=[]
        for model in MODELS:
            rs=[r for r in predictions if r['model']==model];ss=[r for r in rs if r['stress']]
            err=[r['abs_error_bps'] for r in rs]
            rows.append(dict(Model=model,Targets=len(rs),MAE_bps=float(np.mean(err)),RMSE_bps=float(np.sqrt(np.mean(np.square(err)))),Max_error_bps=max(err),Coverage_pct=100*float(np.mean([r['covered'] for r in rs])),Mean_width_bps=float(np.mean([r['width_bps'] for r in rs])),Winkler_bps=float(np.mean([r['winkler_bps'] for r in rs])),Stress_targets=len(ss),Stress_MAE_bps=float(np.mean([r['abs_error_bps'] for r in ss])) if ss else None))
        baseline=next(r['MAE_bps'] for r in rows if r['Model']=='Persistence')
        for r in rows:r['Improvement_pct']=100*(1-r['MAE_bps']/baseline)
        out.append(dict(event=name,asset=asset,start=start,end=end,scores=rows,predictions=predictions,dataset_sha256=result['dataset_sha256'],protocol=result['protocol']))
        print(name,[(r['Model'],round(r['Improvement_pct'],1)) for r in rows],flush=True)
    payload=dict(generated_at_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),seed=419,scope='Retrospective chronological event audit using pre-existing daily provider samples. Specifications chosen after events; not a preregistered untouched event holdout. No onchain covariates or ABM structural parameters are transferred.',source_sha256=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest(),events=out)
    (ROOT/'empirical_data/event_audit.json').write_text(json.dumps(payload,indent=2,allow_nan=False))
if __name__=='__main__':build()
