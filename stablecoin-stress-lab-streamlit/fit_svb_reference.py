import json, hashlib
from pathlib import Path
from datetime import datetime,timedelta
import numpy as np
from scipy.optimize import differential_evolution
from backend.app.domain.schemas import AgentExperimentRequest
from backend.app.services.agents import simulate_agents
root=Path.cwd();rows=json.loads((root/'empirical_data/prices_hourly.json').read_text());obs=sorted((datetime.fromisoformat(r['timestamp'].replace('Z','+00:00')),r['price_usd']) for r in rows if r['asset']=='USDC')
base=AgentExperimentRequest(date='2023-03-10',lp_max_withdrawal_pct=0)
r=simulate_agents(base);
# Match each model hour to the most recent observed sample, never a future observation.
start=datetime.fromisoformat(r['snapshot']['timestamp'].replace('Z','+00:00')) if 'snapshot' in r else None
if start is None:
 from backend.app.services.replay import pool_snapshot_for_date
 start=datetime.fromisoformat(pool_snapshot_for_date(base.date)['timestamp'].replace('Z','+00:00'))
indices=[];target=[];clock=[]
for i in range(1,73):
 cutoff=start+timedelta(hours=i);prior=[(t,p) for t,p in obs if t<=cutoff]
 if prior and (cutoff-prior[-1][0]).total_seconds()<=7200:indices.append(i-1);target.append(prior[-1][1]);clock.append(cutoff.isoformat())
def request(x):return base.model_copy(update=dict(redemption_pressure_pct=float(x[0]),arbitrage_capital_usd=float(x[1]*1e6),lp_max_withdrawal_pct=float(x[2])))
def objective(x):
 result=simulate_agents(request(x));path=[s['pool_implied_usdc_usd_after_agents'] for s in result['steps']];return float(np.mean((np.array(path)[indices]-target)**2))
fit=differential_evolution(objective,[(.001,50),(.1,100),(0,60)],seed=419,maxiter=35,popsize=5,polish=False)
req=request(fit.x);result=simulate_agents(req)
artifact=dict(method='In-sample minimum squared distance; bounded differential evolution, seed 419; 3 effective scenario parameters; other rules fixed',request=req.model_dump(mode='json'),result=result,observed=[dict(hour=i+1,timestamp=t,price=p) for i,t,p in zip(indices,clock,target)],rmse_bps=10000*np.sqrt(fit.fun),dataset_sha256=hashlib.sha256((root/'empirical_data/prices_hourly.json').read_bytes()).hexdigest(),limitations='Single-event in-sample reference fit, not structural identification or out-of-event validation. Hourly observations may miss the intraday low. Global redemption pressure is an assumed-supply percentage, not percent of pool TVL.')
(root/'svb_reference_fit.json').write_text(json.dumps(artifact,separators=(',',':'),default=str))
print(fit.x,artifact['rmse_bps'],min(target),min(s['pool_implied_usdc_usd_after_agents'] for s in result['steps']))
