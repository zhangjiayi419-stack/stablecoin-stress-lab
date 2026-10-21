"""Standalone resumable Curve 3pool archive collection. Public RPC, no keys.
Run: python3 collect_snapshots.py; dependency: requests.
"""
import csv,gzip,hashlib,json,math,re,threading,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
from stable_swap_solver import quote_swap
ROOT=Path(__file__).resolve().parent
RAW=ROOT/'raw_responses';SNAPS=ROOT/'snapshots'
RAW.mkdir(exist_ok=True);SNAPS.mkdir(exist_ok=True)
RPC='https://eth.drpc.org';POOL='0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7'
TLS=threading.local()
def utc(ts):return datetime.fromtimestamp(ts,timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def fetch(url,payload=None):
    key=hashlib.sha256(json.dumps([url,payload],sort_keys=True).encode()).hexdigest();path=RAW/(key+'.json')
    if path.exists():return json.loads(path.read_text())['response'],path.name
    if not hasattr(TLS,'http'):TLS.http=requests.Session()
    for attempt in range(3):
        try:
            r=TLS.http.get(url,timeout=25) if payload is None else TLS.http.post(url,json=payload,timeout=25)
            if r.status_code==429:time.sleep(min(30,float(r.headers.get('Retry-After','5'))))
            r.raise_for_status();data=r.json()
            if isinstance(data,dict) and 'error' in data:raise ValueError(str(data['error']))
            if isinstance(data,list) and any('error' in x for x in data):raise ValueError(str(data))
            doc=dict(url=url,request=payload,retrieved_at_utc=utc(time.time()),response=data)
            temp=path.with_suffix('.tmp-'+str(threading.get_ident()));temp.write_text(json.dumps(doc,separators=(',',':')));temp.replace(path)
            return data,path.name
        except (requests.RequestException,ValueError):
            if attempt==2:raise
            time.sleep(2**attempt)
def rpc(method,params):
    data,key=fetch(RPC,dict(jsonrpc='2.0',id=1,method=method,params=params));return data['result'],key

def enc(selector,*args):return selector+''.join(f'{a:064x}' for a in args)
def snapshot(ts,events):
    path=SNAPS/f'{ts}.json'
    if path.exists():return json.loads(path.read_text())
    refs=[]
    hint,key=fetch('https://coins.llama.fi/block/ethereum/'+str(ts));refs.append(key);block=int(hint['height'])
    header,key=rpc('eth_getBlockByNumber',[hex(block),False]);refs.append(key)
    for _ in range(25):
        if int(header['timestamp'],16)<=ts:break
        block-=1;header,key=rpc('eth_getBlockByNumber',[hex(block),False]);refs.append(key)
    else:raise ValueError('Cannot establish block before cutoff')
    nxt,key=rpc('eth_getBlockByNumber',[hex(block+1),False]);refs.append(key)
    # Check BOTH sides; timestamp resolver may return an approximate height.
    for _ in range(25):
        if int(nxt['timestamp'],16)>ts:break
        block+=1;header=nxt;nxt,key=rpc('eth_getBlockByNumber',[hex(block+1),False]);refs.append(key)
    else:raise ValueError('Cannot establish nearest block')
    selectors=[enc('0x4903b0d1',i) for i in range(3)]+['0xf446c1d0','0xddca3f43',enc('0x5e0d443f',1,2,10**12)]
    vals=[]
    for start in range(0,len(selectors),2):
        payload=[dict(jsonrpc='2.0',id=i,method='eth_call',params=[dict(to=POOL,data=selectors[i]),hex(block)]) for i in range(start,min(start+2,len(selectors)))]
        response,key=fetch(RPC,payload);refs.append(key)
        if sorted(x['id'] for x in response)!=list(range(start,min(start+2,len(selectors)))):raise ValueError('Incomplete batch')
        vals.extend(int(x['result'],16) for x in sorted(response,key=lambda x:x['id']))
    if any(v<=0 for v in vals[:4]) or not 0<=vals[4]<10**10:raise ValueError('Invalid state units')
    row=dict(chain_id=1,contract=POOL,events=events,requested_cutoff_utc=utc(ts),timestamp=utc(int(header['timestamp'],16)),next_block_timestamp=utc(int(nxt['timestamp'],16)),block_number=block,block_hash=header['hash'],cutoff_lag_seconds=ts-int(header['timestamp'],16),raw_dai_balance=str(vals[0]),raw_usdc_balance=str(vals[1]),raw_usdt_balance=str(vals[2]),dai_pool=vals[0]/1e18,usdc_pool=vals[1]/1e6,usdt_pool=vals[2]/1e6,amp=vals[3],fee_rate=vals[4]/1e10,contract_quote_1m_usdc_to_usdt=vals[5]/1e6,source=RPC,retrieved_at_utc=utc(time.time()),raw_response_files=refs)
    model=quote_swap(row,1,2,1e6)['net_output'];row['python_quote_1m_usdc_to_usdt']=model
    row['solver_relative_error_bps']=(model-row['contract_quote_1m_usdc_to_usdt'])/row['contract_quote_1m_usdc_to_usdt']*10000
    if not math.isfinite(row['solver_relative_error_bps']):raise ValueError('Nonfinite solver error')
    path.write_text(json.dumps(row,separators=(',',':')));return row

def targets():
    out={}
    for event,day in [('Terra_2022_05','2022-05-12'),('FTX_2022_11','2022-11-09'),('SVB_2023_03','2023-03-11')]:
        center=datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        for offset in range(-14*24,14*24+1,6):out.setdefault(int((center+timedelta(hours=offset)).timestamp()),set()).add(event)
        for offset in range(-3*24,3*24+1):out.setdefault(int((center+timedelta(hours=offset)).timestamp()),set()).add(event)
    center=datetime(2023,3,11,tzinfo=timezone.utc)
    for offset in range(0,2*24*60+1,15):out.setdefault(int((center+timedelta(minutes=offset)).timestamp()),set()).add('SVB_2023_03')
    return {k:sorted(v) for k,v in sorted(out.items())}

def csv_export(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:writer.writerow({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in row.items()})

def finalize(rows,failures,requested):
    prior=json.loads((ROOT/'prior_346_states.json').read_text())
    prior_blocks={r['block_number'] for r in prior}
    with (ROOT/'prior_73_replay_catalog.csv').open() as f:
        for r in csv.DictReader(f):
            match=re.search(r'block (\d+)',r['source'])
            if match:prior_blocks.add(int(match[1]))
    # Cutoff observations and unique chain states are exported separately.
    unique={r['block_number']:r for r in rows};unique_rows=sorted(unique.values(),key=lambda r:r['block_number'])
    new=[r for r in unique_rows if r['block_number'] not in prior_blocks]
    for name,data in [('cutoff_observations',rows),('unique_pool_states',unique_rows),('new_unique_pool_states',new),('failed_cutoffs',failures)]:
        (ROOT/(name+'.json')).write_text(json.dumps(data,indent=2,allow_nan=False));csv_export(ROOT/(name+'.csv'),data)
    with gzip.open(ROOT/'raw_responses.jsonl.gz','wt') as out:
        for p in sorted(RAW.glob('*.json')):out.write(p.read_text()+'\n')
    per_event={}
    for event in ['Terra_2022_05','FTX_2022_11','SVB_2023_03']:
        rs=[r for r in rows if event in r['events']];ns=[r for r in new if event in r['events']]
        per_event[event]=dict(cutoff_observations=len(rs),unique_blocks=len({r['block_number'] for r in rs}),new_blocks=len(ns),start=min((r['requested_cutoff_utc'] for r in rs),default=None),end=max((r['requested_cutoff_utc'] for r in rs),default=None))
    manifest=dict(dataset='Curve 3pool multi-event historical extension',created_at_utc=utc(time.time()),chain_id=1,contract=POOL,rpc=RPC,requested_cutoffs=len(requested),successful_cutoffs=len(rows),failed_cutoffs=len(failures),unique_blocks=len(unique),new_blocks_vs_prior_73_and_346=len(new),per_event=per_event,maximum_solver_relative_error_bps=max((abs(r['solver_relative_error_bps']) for r in rows),default=None),sampling='6-hour grid over event ±14d; hourly over ±3d; SVB Mar11–13 additionally every15min. Both endpoints included.',alignment='block timestamp <= cutoff < next block timestamp, verified using RPC headers. All eth_call state at the same block number.',limitations=['One pool only; more timestamps do not add independent events.','Pool amounts are tokens, not independently USD-valued TVL.','No USD-price path, swap/LP-event collection or behavioral calibration is included in this extension.','Floating-point solver is checked only for 1m USDC to USDT at each collected state.','Prior catalog is copied for reference; it is not counted as newly collected data.'],files={p.name:sha(p) for p in ROOT.iterdir() if p.is_file() and p.name not in {'manifest.json','validation_report.json'}})
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2));print('FINAL',json.dumps({k:manifest[k] for k in ['successful_cutoffs','failed_cutoffs','unique_blocks','new_blocks_vs_prior_73_and_346','maximum_solver_relative_error_bps']}),flush=True)

def main():
    requested=targets();print('TARGETS',len(requested),flush=True);rows=[];failures=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        tasks={ex.submit(snapshot,ts,events):ts for ts,events in requested.items()}
        for i,f in enumerate(as_completed(tasks),1):
            ts=tasks[f]
            try:rows.append(f.result())
            except Exception as err:
                failures.append(dict(cutoff_utc=utc(ts),events=requested[ts],error=str(err)));print('FAIL',utc(ts),str(err)[:150],flush=True)
            if i%25==0:print('PROGRESS',i,'/',len(requested),'ok',len(rows),'failed',len(failures),flush=True)
    rows.sort(key=lambda r:r['requested_cutoff_utc']);finalize(rows,failures,requested)
if __name__=='__main__':main()
