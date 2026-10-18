"""Chronological SETAR and bounded adaptive conformal intervals; no performance promises."""
import json,math,hashlib
from pathlib import Path
import numpy as np
from model_lab import predict,features
VERSION='econometrics-2.0'
MODELS=['Persistence','Rolling mean (7d)','AR(1)','SETAR','Gradient boosting']


def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()


def setar_fit(values):
    v=(np.asarray(values)-1)*10000;x=v[:-1];y=v[1:]
    def estimate(xx,yy):
        if len(xx)<5:return None
        den=float(np.sum((xx-xx.mean())**2))
        phi=float(np.clip(np.sum((xx-xx.mean())*(yy-yy.mean()))/den,-.98,.98)) if den>1e-12 else 0.
        return float(yy.mean()-phi*xx.mean()),phi
    fallback=estimate(x,y);best=None
    for threshold in np.unique(np.quantile(abs(x),[.5,.65,.8])):
        high=abs(x)>threshold;low=~high
        lo=estimate(x[low],y[low]);hi=estimate(x[high],y[high])
        if lo is None or hi is None:continue
        fitted=np.where(high,hi[0]+hi[1]*x,lo[0]+lo[1]*x)
        loss=float(np.mean((fitted-y)**2))
        if best is None or loss<best[0]:best=(loss,float(threshold),lo,hi)
    return dict(threshold_bps=best[1],low=best[2],high=best[3]) if best else dict(threshold_bps=0.,low=fallback,high=fallback)


def point(values,model,horizon):
    if model!='SETAR':return predict(values,model,horizon)[-1]
    fit=setar_fit(values);v=(values[-1]-1)*10000
    for _ in range(horizon):
        a,p=fit['high'] if abs(v)>fit['threshold_bps'] else fit['low'];v=a+p*v
    return 1+v/10000


def winkler(actual,lower,upper,alpha=.1):
    return upper-lower+2/alpha*max(0.,lower-actual)+2/alpha*max(0.,actual-upper)


def evaluate_intervals(items,horizon=1,mode='Bounded ACI',models=None,points=None):
    """At origin i only errors with target index <i can calibrate the interval.

    Warm-up: 30 observations, then 20 resolved OOS residuals. ACI feedback is
    applied only when the corresponding target has become observable.
    """
    if horizon not in (1,3,7):raise ValueError('Supported horizons are 1,3,7')
    if len(items)<60:raise ValueError('At least 60 consecutive observations are needed for interval evaluation.')
    values=[float(r[1]) for r in items];dates=[str(r[0]) for r in items];models=models or MODELS
    all_rows=[];forecasts={};settings={}
    for model in models:
        residuals=[];pending=[];alpha=.1;rows=[]
        for i in range(30,len(values)+1):
            for r in list(pending):
                if r['target_index']<i:
                    actual=values[r['target_index']];residuals.append(abs(actual-r['prediction_usd']))
                    if r['lower_usd'] is not None and mode=='Bounded ACI':
                        miss=float(not r['lower_usd']<=actual<=r['upper_usd'])
                        alpha=float(np.clip(alpha+.02*(.1-miss),.005,.5))
                    pending.remove(r)
            train=values[max(0,i-90):i]
            pred=float(points[model][str(i)]) if points is not None else point(train,model,horizon)
            lower=upper=None;alpha_used=None
            if len(residuals)>=20:
                calibration=sorted(residuals[-60:]);alpha_used=max(1/(len(calibration)+1),min(.5,alpha if mode=='Bounded ACI' else .1))
                rank=min(len(calibration),math.ceil((len(calibration)+1)*(1-alpha_used)))
                width=calibration[rank-1];lower=pred-width;upper=pred+width
            r=dict(model=model,origin=dates[i-1],target_index=i+horizon-1,prediction_usd=pred,lower_usd=lower,upper_usd=upper,
                calibration_count=min(60,len(residuals)),alpha_used=alpha_used)
            pending.append(r)
            if i+horizon-1<len(values) and lower is not None:
                actual=values[i+horizon-1];r={**r,'target':dates[i+horizon-1],'actual_usd':actual,
                    'abs_error_bps':abs(pred-actual)*10000,'covered':lower<=actual<=upper,
                    'width_bps':(upper-lower)*10000,'winkler_bps':winkler(actual,lower,upper)*10000,
                    'stress':abs(actual-1)>.01}
                rows.append(r)
            if i==len(values):forecasts[model]=r
        all_rows+=rows
        if model=='SETAR':settings[model]=setar_fit(values[-90:])
    common=set.intersection(*[{r['origin'] for r in all_rows if r['model']==model} for model in models])
    all_rows=[r for r in all_rows if r['origin'] in common]
    scores=[]
    for model in models:
        rs=[r for r in all_rows if r['model']==model]
        if not rs:raise ValueError('Insufficient resolved residuals for a common evaluation window.')
        stress=[r for r in rs if r['stress']]
        scores.append(dict(Model=model,Targets=len(rs),MAE_bps=float(np.mean([r['abs_error_bps'] for r in rs])),
            Coverage_pct=float(np.mean([r['covered'] for r in rs])*100),Mean_width_bps=float(np.mean([r['width_bps'] for r in rs])),
            Winkler_bps=float(np.mean([r['winkler_bps'] for r in rs])),Stress_targets=len(stress),
            Stress_MAE_bps=float(np.mean([r['abs_error_bps'] for r in stress])) if stress else None))
    baseline=next(s['MAE_bps'] for s in scores if s['Model']=='Persistence')
    for s in scores:s['Improvement_pct']=100*(1-s['MAE_bps']/baseline) if baseline else None
    return dict(version=VERSION,horizon=horizon,calibration=mode,dataset_sha256=digest(items),scores=sorted(scores,key=lambda s:s['MAE_bps']),
        predictions=all_rows,forecast=forecasts,model_settings=settings,
        protocol='30-point training warmup; ≥20 resolved chronological residuals; last 60 residuals; gamma=0.02; bounded alpha in [0.005,0.5] with finite-quantile floor 1/(n+1). Nominal 90% intervals; empirical coverage only; no per-event coverage guarantee.')
