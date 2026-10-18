"""Decode observed Curve flows; block-time alignment; real contract quote benchmarks."""
import json,bisect,math,gzip
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import defaultdict
import numpy as np
from eth_hash.auto import keccak
from backend.app.domain.stable_swap import quote_swap,get_D
from collect_empirical import OUT,POOL,RPC,encode,calls,rpc,utc
from econometrics import digest
SCALE=[1e18,1e6,1e6];TOKENS=['DAI','USDC','USDT']
EVENTS={
 'TokenExchange(address,int128,uint256,int128,uint256)':'swap',
 'AddLiquidity(address,uint256[3],uint256[3],uint256,uint256)':'add',
 'RemoveLiquidity(address,uint256[3],uint256[3],uint256)':'remove',
 'RemoveLiquidityOne(address,uint256,uint256)':'remove_one',
 'RemoveLiquidityImbalance(address,uint256[3],uint256[3],uint256,uint256)':'remove_imbalance'}
TOPICS={'0x'+keccak(s.encode()).hex():name for s,name in EVENTS.items()}

def load(name):
    path=OUT/name
    if path.exists():return json.loads(path.read_text())
    return json.loads(gzip.decompress(path.with_name(path.name+'.gz').read_bytes()))
def save(name,data):(OUT/name).write_text(json.dumps(data,separators=(',',':'),allow_nan=False))
def ts(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())


def process():
    prices=load('prices_hourly.json');states=load('pool_states.json');events=load('pool_events.json')
    by_asset={a:sorted([r for r in prices if r['asset']==a],key=lambda r:r['unix']) for a in TOKENS}
    def price_at(asset,cutoff):
        series=by_asset[asset];idx=bisect.bisect_right([r['unix'] for r in series],cutoff)-1
        if idx<0 or cutoff-series[idx]['unix']>7200:return None
        return series[idx]
    daily=[]
    groups=defaultdict(list)
    for r in prices:groups[(r['asset'],r['timestamp'][:10])].append(r)
    for (a,d),rows in sorted(groups.items()):
        latest=max(rows,key=lambda r:r['unix'])
        daily.append(dict(asset=a,date_utc=d,close_usd=latest['price_usd'],observation_utc=latest['timestamp'],hourly_count=len(rows)))
    save('stress_daily.json',daily)
    decoded=[]
    for e in events:
        event=TOPICS.get(e['topics'][0]);words=[int(e['data'][i:i+64],16) for i in range(2,len(e['data']),64)]
        if not event:continue
        r=dict(event=event,block_number=int(e['blockNumber'],16),transaction_hash=e['transactionHash'],log_index=int(e['logIndex'],16))
        if event=='swap':
            i,amount,j,out=words;r.update(sold_id=i,bought_id=j,input_tokens=amount/SCALE[i],output_tokens=out/SCALE[j])
        elif event in ('add','remove','remove_imbalance'):
            r.update(token_amounts=[words[i]/SCALE[i] for i in range(3)],lp_supply_raw=words[-1])
        else:r.update(lp_burned_raw=words[0],output_amount_raw=words[1])
        decoded.append(r)
    decoded.sort(key=lambda r:(r['block_number'],r['log_index']));save('decoded_events.json',decoded)
    hourly=sorted([s for s in states if s['cutoff_utc'][11:]=='00:00:00Z' or s['cutoff_utc'][14:]=='00:00Z'],key=lambda s:s['block_number'])
    # Hourly cutoffs include exactly :00:00; daily :59:59 observations are excluded.
    hourly=[s for s in states if s['cutoff_utc'][14:]=='00:00Z'];hourly.sort(key=lambda s:s['block_number'])
    blocks=[e['block_number'] for e in decoded];features=[];alignment_exclusions=[]
    for previous,state in zip(hourly,hourly[1:]):
        cutoff=ts(state['cutoff_utc']);sblock=state['block_number'];end=ts(state['timestamp'])
        observations={a:price_at(a,cutoff) for a in TOKENS}
        if any(r is None for r in observations.values()):
            alignment_exclusions.append(dict(cutoff_utc=state['cutoff_utc'],reason='No prior USD sample within 2h for '+','.join(a for a,r in observations.items() if r is None)))
            continue
        if any(r['unix']>cutoff for r in observations.values()):raise ValueError('Future price alignment')
        interval=decoded[bisect.bisect_right(blocks,previous['block_number']):bisect.bisect_right(blocks,sblock)]
        marked=[state[a.lower()+'_pool']*observations[a]['price_usd'] for a in TOKENS]
        weights=np.array(marked)/sum(marked);imbalance=float(np.abs(weights-1/3).sum()/2)
        qsmall=quote_swap(state,1,2,10000.);qlarge=quote_swap(state,1,2,1000000.)
        vol=0.;net_usdc=0.;lp_add=lp_remove=0.;one_count=0
        for e in interval:
            if e['event']=='swap':
                vol+=e['input_tokens']*observations[TOKENS[e['sold_id']]]['price_usd']
                if e['sold_id']==1:net_usdc+=e['input_tokens']
                if e['bought_id']==1:net_usdc-=e['output_tokens']
            elif e['event'] in ('add','remove','remove_imbalance'):
                value=sum(v*observations[a]['price_usd'] for a,v in zip(TOKENS,e['token_amounts']))
                if e['event']=='add':lp_add+=value
                else:lp_remove+=value
            else:one_count+=1
        # Independent LP net-flow proxy in invariant units; swaps mostly preserve D,
        # fees/A effects mean this is not an exact withdrawal accounting identity.
        previous_d=get_D([previous[k] for k in ('dai_pool','usdc_pool','usdt_pool')],previous['amp'])
        current_d=get_D([state[k] for k in ('dai_pool','usdc_pool','usdt_pool')],state['amp'])
        trailing=[r['swap_volume_usd'] for r in features[-24:]]
        spike=vol/np.mean(trailing) if trailing and np.mean(trailing)>0 else 1.
        features.append(dict(cutoff_utc=state['cutoff_utc'],state_utc=state['timestamp'],block_number=sblock,block_hash=state['block_hash'],
            price_usdc=observations['USDC']['price_usd'],price_usdt=observations['USDT']['price_usd'],
            price_usdc_observed_at=observations['USDC']['timestamp'],price_usdt_observed_at=observations['USDT']['timestamp'],
            imbalance_ratio=imbalance,swap_volume_usd=vol,volume_spike=float(spike),net_usdc_input=net_usdc,
            slippage_slope_bps_per_million=(qsmall['average_execution_price_net']-qlarge['average_execution_price_net'])*10000/.99,
            lp_add_usd=lp_add,lp_remove_multi_usd=lp_remove,lp_remove_one_events=one_count,
            invariant_units=current_d,net_invariant_withdrawal_proxy_pct=max(0.,1-current_d/previous_d)*100,
            tvl_marked_usd=sum(marked),pool_quote_usdc_usdt=state['contract_quote_1m_usdc_to_usdt']/1e6,
            source_interval_from_block=previous['block_number']+1,source_interval_to_block=sblock))
    save('microstructure_features.json',features)
    # Five actual historical blocks, three amounts and two directions, 30 contract calls.
    desired=['2023-03-09T00:00:00Z','2023-03-10T18:00:00Z','2023-03-11T08:00:00Z','2023-03-12T12:00:00Z','2023-03-15T00:00:00Z']
    benchmarks=[]
    for target in desired:
        state=next(s for s in states if s['cutoff_utc']==target);block=state['block_number']
        configurations=[(i,j,amount) for i,j in [(1,2),(2,1)] for amount in [10000,1000000,10000000]]
        observed=calls(block,[encode('0x5e0d443f',i,j,amount*10**6) for i,j,amount in configurations])
        for (i,j,amount),raw in zip(configurations,observed):
            modeled=quote_swap(state,i,j,float(amount))['net_output'];actual=raw/1e6
            benchmarks.append(dict(block_number=block,block_hash=state['block_hash'],block_time=state['timestamp'],
                direction=TOKENS[i]+' → '+TOKENS[j],input_tokens=amount,contract_output_raw=str(raw),contract_output_tokens=actual,
                python_output_tokens=modeled,relative_error_bps=(modeled-actual)/actual*10000,
                absolute_error_tokens=abs(modeled-actual),contract=POOL,method='eth_call get_dy(int128,int128,uint256) at exact block'))
    save('contract_benchmarks.json',benchmarks)
    crosschecks=[]
    ordered=sorted(events,key=lambda e:(int(e['blockNumber'],16),int(e['logIndex'],16)))
    for index in np.linspace(0,len(ordered)-1,5,dtype=int):
        event=ordered[int(index)];receipt=rpc('eth_getTransactionReceipt',[event['transactionHash']])
        matching=next((l for l in receipt['logs'] if int(l['logIndex'],16)==int(event['logIndex'],16)),None)
        match=bool(matching and matching['data'].lower()==event['data'].lower() and matching['topics'][0].lower()==event['topics'][0].lower() and matching['address'].lower()==POOL)
        if not match:raise ValueError('Indexer log disagrees with independent RPC receipt')
        crosschecks.append(dict(transaction_hash=event['transactionHash'],log_index=int(event['logIndex'],16),block_number=int(event['blockNumber'],16),block_hash=receipt['blockHash'],rpc_receipt_match=match))
    save('event_crosschecks.json',crosschecks)

    manifest=dict(retrieved_at_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),pool=POOL,rpc=RPC,
        price_source='DefiLlama price chart API, coingecko IDs usd-coin / tether / dai',
        log_source='https://eth.drpc.org — eth_getLogs, complete supported swap/LP event topics in consecutive ≤100-block subranges',state_count=len(states),hourly_feature_count=len(features),raw_event_count=len(events),decoded_event_count=len(decoded),price_observations=len(prices),
        daily_range=['2023-01-01','2023-04-15'],hourly_state_range=['2023-03-07','2023-03-17'],
        alignment_exclusions=alignment_exclusions,independent_receipt_crosschecks=len(crosschecks),contract_blocks=len(desired),contract_quotes=len(benchmarks),maximum_solver_error_bps=max(abs(r['relative_error_bps']) for r in benchmarks),
        clocks='State block <= hourly cutoff; last observed USD sample <= cutoff and ≤2h old; log intervals (previous block,current block]; predictors at t target price at t+1.',
        limitations=['Single pool and single crisis event; no causal identification.','Prices are provider samples, not exchange OHLC.','USD-marked volume uses interval-end known prices; feature available only at cutoff.','Net invariant withdrawal proxy is affected by fees and amplification; not exact LP flow.','Single-coin removal event has no token ID; its USD amount is not invented.'],
        files={name:digest(load(name)) for name in ['stress_daily.json','prices_hourly.json','pool_states.json','pool_events.json','decoded_events.json','microstructure_features.json','contract_benchmarks.json','event_crosschecks.json']})
    save('manifest.json',manifest)
    print(json.dumps({k:v for k,v in manifest.items() if k not in ('files','limitations')},indent=2),flush=True)

if __name__=='__main__':process()
