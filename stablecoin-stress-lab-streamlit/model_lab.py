"""Comparable rolling-origin forecasts. Prices modeled as USD-peg deviations (bps)."""
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path
from forecast_brief import clean_series, fit
VERSION='model-lab-1.0'
MODELS=['Persistence','Rolling mean (7d)','AR(1)','Gradient boosting']


def fingerprint(rows):
    canonical=[(asset,[(d.isoformat(),v) for d,v in clean_series(rows,asset)]) for asset in ('USDC','USDT')]
    return hashlib.sha256(json.dumps(canonical,separators=(',',':')).encode()).hexdigest()


def features(v):
    tail=v[-7:]
    return [v[-1],v[-2],v[-3],v[-7],statistics.mean(tail),statistics.pstdev(tail),v[-1]-v[-2]]


def predict(values, model, horizon):
    values=list(values)
    if len(values)<30:raise ValueError('At least 30 training observations required.')
    if horizon not in (1,3,7):raise ValueError('Unsupported horizon')
    if model=='Persistence':return [values[-1]]*horizon
    if model=='Rolling mean (7d)':return [statistics.mean(values[-7:])]*horizon
    bps=[(v-1)*10000 for v in values]
    if model=='AR(1)':
        a,phi,_=fit(bps);result=[];v=bps[-1]
        for _ in range(horizon):v=a+phi*v;result.append(1+v/10000)
        return result
    if model!='Gradient boosting':raise ValueError('Unknown model')
    from sklearn.ensemble import GradientBoostingRegressor
    x=[features(bps[:i]) for i in range(7,len(bps))];y=bps[7:]
    reg=GradientBoostingRegressor(n_estimators=50,max_depth=2,min_samples_leaf=5,learning_rate=.05,loss='huber',random_state=419)
    reg.fit(x,y);result=[]
    for _ in range(horizon):
        v=float(reg.predict([features(bps)])[0]);bps.append(v);result.append(1+v/10000)
    return result


def origins(n):
    # Same most recent 20 origins for every horizon; every 7d target is observable.
    return list(range(max(30,n-7-19),n-7+1))


def evaluate(rows, asset, horizon=1, chronos=None):
    items=clean_series(rows,asset);values=[v for _,v in items];details=[]
    if items[-1][0]>datetime.now(timezone.utc).date():raise ValueError('Future observations are not allowed.')
    for i in origins(len(values)):
        for model in MODELS:
            point=predict(values[:i],model,horizon)[-1]
            details.append(dict(model=model,origin=items[i-1][0].isoformat(),target=items[i+horizon-1][0].isoformat(),actual_usd=values[i+horizon-1],prediction_usd=point))
        if chronos:
            key=items[i-1][0].isoformat()
            point=chronos['backtests'][asset][key][horizon-1]
            details.append(dict(model='Chronos-2',origin=key,target=items[i+horizon-1][0].isoformat(),actual_usd=values[i+horizon-1],prediction_usd=point))
    scores=[]
    baseline=statistics.mean(abs(r['prediction_usd']-r['actual_usd'])*10000 for r in details if r['model']=='Persistence')
    for model in MODELS+(['Chronos-2'] if chronos else []):
        group=[r for r in details if r['model']==model]
        errors=[(r['prediction_usd']-r['actual_usd'])*10000 for r in group]
        stress=[abs((r['prediction_usd']-r['actual_usd'])*10000) for r in group if abs(r['actual_usd']-1)>=.01]
        mae=statistics.mean(map(abs,errors))
        scores.append(dict(model=model,n=len(errors),mae_bps=mae,rmse_bps=math.sqrt(statistics.mean(e*e for e in errors)),worst_error_bps=max(map(abs,errors)),improvement_pct=100*(1-mae/baseline) if baseline else None,stress_n=len(stress),stress_mae_bps=statistics.mean(stress) if stress else None))
    projections=[]
    for model in MODELS+(['Chronos-2'] if chronos else []):
        path=chronos['forecast'][asset]['median'][:horizon] if model=='Chronos-2' else predict(values,model,horizon)
        for h,point in enumerate(path,1):
            projections.append(dict(model=model,date_utc=(items[-1][0]+timedelta(days=h)).isoformat(),prediction_usd=point,deviation_bps=(point-1)*10000))
    return dict(version=VERSION,dataset_sha256=fingerprint(rows),asset=asset,horizon_days=horizon,as_of=items[-1][0].isoformat(),observations=len(items),
        evaluation='Expanding chronological contexts, identical last ≤20 origins, endpoint errors at selected horizon; overlapping targets are dependent.',
        scores=sorted(scores,key=lambda r:r['mae_bps']),predictions=details,projections=projections,
        training_config=dict(rolling_window=7,ar_phi_bounds=[-.98,.98],boosting=dict(n_estimators=50,max_depth=2,min_samples_leaf=5,learning_rate=.05,loss='huber',random_state=419)),
        chronos_metadata=chronos.get('metadata') if chronos else None)


def saved_chronos(rows):
    path=Path(__file__).with_name('chronos_snapshot.json')
    if not path.exists():return None
    artifact=json.loads(path.read_text())
    if artifact.get('dataset_sha256')!=fingerprint(rows):return None
    return artifact
