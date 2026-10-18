"""Execute reproducible evaluation, covariate ablations, partial MDE and canonical runs."""
import json,math
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from scipy.optimize import lsq_linear
from econometrics import evaluate_intervals,point,MODELS,digest
from forecast_brief import clean_series
from model_lab import features
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'empirical_data'

def load(name):return json.loads((OUT/name).read_text())
def save(name,obj):(OUT/name).write_text(json.dumps(obj,separators=(',',':'),allow_nan=False))


def evaluate_daily():
    stress=load('stress_daily.json');recent=json.loads((ROOT/'reports/prices_latest.json').read_text());results={};contexts={}
    for regime,source in [('recent',recent),('svb',stress)]:
        for asset in ('USDC','USDT'):
            if regime=='recent':items=[(d.isoformat(),v) for d,v in clean_series(source,asset)]
            else:items=sorted((r['date_utc'],r['close_usd']) for r in source if r['asset']==asset)
            if any((datetime.fromisoformat(b[0])-datetime.fromisoformat(a[0])).days!=1 for a,b in zip(items,items[1:])):raise ValueError('Daily observation gap')
            contexts[regime+'|'+asset]=dict(as_of=items[-1][0],latest_usd=items[-1][1],observations=len(items))
            for h in (1,3,7):
                predictions={m:{str(i):point([v for _,v in items[max(0,i-90):i]],m,h) for i in range(30,len(items)+1)} for m in MODELS}
                for mode in ['Rolling conformal','Bounded ACI']:
                    key=f'{regime}|{asset}|{h}|{mode}';results[key]=evaluate_intervals(items,h,mode,points=predictions)
                print('Daily evaluation',regime,asset,h,flush=True)
    save('econometric_results.json',dict(generated_at_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),recent_sha256=digest(recent),contexts=contexts,results=results))


def covariates():
    data=load('microstructure_features.json');results={}
    for asset in ('USDC','USDT'):
        field='price_'+asset.lower();y=np.array([(r[field]-1)*10000 for r in data]);rows=[]
        stamps=[datetime.fromisoformat(r['cutoff_utc']).timestamp() for r in data]
        valid=lambda j: stamps[j+1]-stamps[j]==3600 and stamps[j]-stamps[j-6]==6*3600
        for i in range(60,len(data)-1):
            if not valid(i):continue
            # Model at cutoff i predicts cutoff i+1. Training labels stop at cutoff i.
            train=[j for j in range(7,i) if valid(j)];test=i
            for cov in [False,True]:
                def design(j):
                    base=features(y[:j+1].tolist())
                    if cov:base += [data[j][f] for f in ('imbalance_ratio','volume_spike','slippage_slope_bps_per_million')]
                    return base
                reg=GradientBoostingRegressor(n_estimators=50,max_depth=2,min_samples_leaf=5,loss='huber',learning_rate=.05,random_state=419)
                reg.fit([design(j) for j in train],[y[j+1] for j in train])
                pred=float(reg.predict([design(test)])[0]);actual=float(y[i+1])
                rows.append(dict(model='GB + observed covariates' if cov else 'GB price-only',origin=data[i]['cutoff_utc'],target=data[i+1]['cutoff_utc'],prediction_bps=pred,actual_bps=actual,abs_error_bps=abs(pred-actual),stress=abs(actual)>100))
            actual=float(y[i+1]);rows.append(dict(model='Persistence',origin=data[i]['cutoff_utc'],target=data[i+1]['cutoff_utc'],prediction_bps=float(y[i]),actual_bps=actual,abs_error_bps=abs(float(y[i])-actual),stress=abs(actual)>100))
        scores=[]
        for model in ['Persistence','GB price-only','GB + observed covariates']:
            rs=[r for r in rows if r['model']==model];ss=[r for r in rs if r['stress']]
            scores.append(dict(Model=model,Targets=len(rs),MAE_bps=float(np.mean([r['abs_error_bps'] for r in rs])),Stress_targets=len(ss),Stress_MAE_bps=float(np.mean([r['abs_error_bps'] for r in ss])) if ss else None))
        baseline=scores[0]['MAE_bps']
        for r in scores:r['Improvement_pct']=100*(1-r['MAE_bps']/baseline) if baseline else None
        results[asset]=dict(scores=sorted(scores,key=lambda r:r['MAE_bps']),predictions=rows)
        print('Covariate ablation',asset,scores,flush=True)
    save('covariate_results.json',dict(feature_sha256=digest(data),results=results,
        specification='One-hour-ahead peg deviation; first 60 cutoffs warmup; expanding fit; lags + observed imbalance/volume-spike/slippage; no tuning on evaluation; full last-observed feature at t predicts t+1; require consecutive one-hour targets and seven-observation lag windows; missing intervals are excluded, not interpolated; one crisis, dependent errors.'))


def estimate_response():
    data=load('microstructure_features.json');x=[];y=[];times=[]
    for prev,row in zip(data,data[1:]):
        if (datetime.fromisoformat(row['cutoff_utc'])-datetime.fromisoformat(prev['cutoff_utc'])).total_seconds()!=3600:continue
        x.append([1.,max(0,1-prev['price_usdc'])*100,prev['net_invariant_withdrawal_proxy_pct']])
        y.append(row['net_invariant_withdrawal_proxy_pct']);times.append(row['cutoff_utc'])
    x=np.asarray(x);y=np.asarray(y);split=int(len(y)*.7)
    fit=lsq_linear(x[:split],y[:split],bounds=(0,np.inf));pred=x[split:]@fit.x
    rng=np.random.default_rng(419);coeffs=[]
    # Moving blocks of six hours, resampled only from the training segment.
    for _ in range(100):
        eligible=[s for s in range(split-6+1) if (datetime.fromisoformat(times[s+5])-datetime.fromisoformat(times[s])).total_seconds()==5*3600]
        starts=rng.choice(eligible,size=math.ceil(split/6));idx=np.concatenate([np.arange(s,s+6) for s in starts])[:split]
        coeffs.append(lsq_linear(x[idx],y[idx],bounds=(0,np.inf)).x)
    interval=np.quantile(np.asarray(coeffs),[.05,.95],axis=0)
    result=dict(method='Constrained minimum squared-distance fit, nonnegative coefficients; partial effective flow response, not structural agent identification.',
        equation='withdrawal_proxy_pct[t+1] = c + beta * USDC_discount_pct[t] + rho * withdrawal_proxy_pct[t]',
        coefficients=dict(zip(['intercept_pct','discount_response','withdrawal_persistence'],map(float,fit.x))),
        bootstrap_90=dict(zip(['intercept_pct','discount_response','withdrawal_persistence'],interval.T.tolist())),
        seed=419,train_n=split,test_n=len(y)-split,train_end=times[split-1],test_start=times[split],
        holdout_mae_pct=float(np.mean(abs(pred-y[split:]))),zero_response_mae_pct=float(np.mean(abs(y[split:]))),
        feature_sha256=digest(data),limitations='Invariant changes confound LP net flows, fees and A; no individual panic parameter, redemption delay or causal response is identified. Coefficients are not substituted into the ABM as if structurally calibrated.')
    save('response_estimation.json',result);print('Partial MDE',result['coefficients'],flush=True)


def canonical():
    from backend.app.domain.schemas import AgentExperimentRequest
    from backend.app.services.agents import simulate_agents,phase_diagram
    request=AgentExperimentRequest(date='2023-03-11',lp_max_withdrawal_pct=30);state=load('manifest.json');metadata=dict(solver_precision='IEEE-754 float64; approximate historical Curve solver',clock_alignment='Historical pool block versus independent daily USD observations; not synchronized; retained source times',reproducibility_seed=42,dataset_sha256=digest(state),code_version='empirical-workspace-2.0')
    benchmarks=[]
    for kind,result in [('Multi-cohort SVB reference',simulate_agents(request)),('42-cell pressure × depth grid',phase_diagram(request)),('Exact-block contract quote comparison',load('contract_benchmarks.json'))]:
        payload=dict(kind='[Canonical Benchmark] '+kind,request=request.model_dump(mode='json') if isinstance(result,dict) and 'assumptions' in result else dict(contract=state['pool'],blocks=5),result=result,metadata=metadata)
        benchmarks.append(dict(run_id=digest(payload)[:12],created_at_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),**payload))
    (ROOT/'canonical_benchmarks.json').write_text(json.dumps(benchmarks,separators=(',',':'),default=str))
    print('Three canonical runs executed',flush=True)

if __name__=='__main__':
    evaluate_daily();covariates();estimate_response();canonical()
