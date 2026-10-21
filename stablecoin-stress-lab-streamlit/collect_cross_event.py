"""Collect real price/flow/header covariates for fixed cross-event protocol.
Resumable cache, four workers, public data only, raw responses preserved.
"""
import json,gzip,hashlib,time,threading
from pathlib import Path
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'cross_event_study';RAW=OUT/'raw';RAW.mkdir(parents=True,exist_ok=True)
RPC='https://eth.drpc.org';POOL='0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7'
TLS=threading.local()
SIGNATURES=['TokenExchange(address,int128,uint256,int128,uint256)','AddLiquidity(address,uint256[3],uint256[3],uint256,uint256)','RemoveLiquidity(address,uint256[3],uint256[3],uint256)','RemoveLiquidityOne(address,uint256,uint256)','RemoveLiquidityImbalance(address,uint256[3],uint256[3],uint256,uint256)']
TOPICS=['0x8b3e96f2b889fa771c53c981b40daf005f63f637f1869f707052d15a3dd97140', '0x423f6495a08fc652425cf4ed0d1f9e37e571d9b9529b1c1c23cce780b2e7df0d', '0xa49d4cf02656aebf8c771f5a8585638a2a15ee6c97cf7205d4208ed7c1df252d', '0x9e96dd3b997a2a257eec4df9bb6eaf626e206df5f543bd963682d143300be310', '0x173599dbf9c6ca6f7c3b590df07ae98a45d74ff54065505141e7de6c46a624c2']
def utc(ts):return datetime.fromtimestamp(ts,timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
def stamp(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())
def fetch(url,payload=None):
 key=hashlib.sha256(json.dumps([url,payload],sort_keys=True).encode()).hexdigest();path=RAW/(key+'.json')
 if path.exists():return json.loads(path.read_text())['response']
 old=ROOT/'archive_extension/raw_responses'/(key+'.json')
 if old.exists():
  path.write_bytes(old.read_bytes());return json.loads(path.read_text())['response']
 if not hasattr(TLS,'http'):TLS.http=requests.Session()
 for attempt in range(3):
  try:
   r=TLS.http.get(url,timeout=30) if payload is None else TLS.http.post(url,json=payload,timeout=30)
   if r.status_code==429:time.sleep(min(30,float(r.headers.get('Retry-After',5))))
   r.raise_for_status();data=r.json()
   if isinstance(data,dict) and 'error' in data:raise ValueError(str(data['error']))
   doc=dict(url=url,request=payload,retrieved_at_utc=utc(time.time()),response=data)
   temp=path.with_suffix('.tmp-'+str(threading.get_ident()));temp.write_text(json.dumps(doc,separators=(',',':')));temp.replace(path)
   return data
  except (requests.RequestException,ValueError):
   if attempt==2:raise
   time.sleep(2**attempt)
def rpc(method,params):return fetch(RPC,dict(jsonrpc='2.0',id=1,method=method,params=params))['result']
def selected_states():
 protocol=json.loads((OUT/'protocol.json').read_text());all_states=json.loads((ROOT/'archive_extension/unique_pool_states.json').read_text());groups={}
 for event,day in protocol['events'].items():
  center=stamp(day+'T00:00:00Z');groups[event]=sorted([r for r in all_states if event in r['events'] and center-72*3600<=stamp(r['requested_cutoff_utc'])<=center+72*3600 and r['requested_cutoff_utc'][14:]=='00:00Z'],key=lambda r:r['block_number'])
  if len(groups[event])!=145:raise ValueError('Incomplete hourly grid '+event)
 return groups
def interval(job):
 event,left,right=job;p=OUT/'log_intervals'/f'{left}-{right}.json'
 if p.exists():return json.loads(p.read_text())
 logs=[]
 for start in range(left,right+1,100):
  chunk=rpc('eth_getLogs',[dict(address=POOL,fromBlock=hex(start),toBlock=hex(min(start+99,right)),topics=[TOPICS])])
  if len(chunk)>=1000:raise ValueError('RPC log response cap reached; interval not accepted')
  if any(r.get('removed') or not left<=int(r['blockNumber'],16)<=right or r['address'].lower()!=POOL for r in chunk):raise ValueError('Invalid historical log')
  logs.extend(chunk)
 unique={(r['transactionHash'],r['logIndex']):r for r in logs}
 result=dict(event=event,from_block=left,to_block=right,logs=list(unique.values()))
 p.write_text(json.dumps(result,separators=(',',':')));return result

def main():
 groups=selected_states();prices=[];jobs=[];headers=[]
 for event,states in groups.items():
  center=stamp(json.loads((OUT/'protocol.json').read_text())['events'][event]+'T00:00:00Z')
  if event=='SVB_2023_03':
   prior=json.loads((ROOT/'empirical_data/prices_hourly.json').read_text())
   prices += [{**r,'event':event,'source_kind':'previously archived provider samples'} for r in prior if center-96*3600<=r['unix']<=center+96*3600]
  else:
   for start in [center-96*3600,center]:
    url=f'https://coins.llama.fi/chart/coingecko:usd-coin,coingecko:tether,coingecko:dai?start={start}&span=96&period=1h&searchWidth=30m'
    data=fetch(url)
    for coin,info in data['coins'].items():
     for p in info['prices']:
      prices.append(dict(event=event,timestamp=utc(p['timestamp']),unix=p['timestamp'],asset={'coingecko:usd-coin':'USDC','coingecko:tether':'USDT','coingecko:dai':'DAI'}[coin],price_usd=p['price'],source=url,source_kind='newly collected provider samples'))
  print('Prices ready',event,flush=True)
  for state in states:
   header=rpc('eth_getBlockByNumber',[hex(state['block_number']),False])
   if header['hash']!=state['block_hash']:raise ValueError('State/header hash mismatch')
   headers.append(dict(event=event,block_number=state['block_number'],block_hash=header['hash'],base_fee_gwei=int(header['baseFeePerGas'],16)/1e9,timestamp=utc(int(header['timestamp'],16))))
  print('Gas headers ready',event,flush=True)
  if event!='SVB_2023_03':jobs += [(event,a['block_number']+1,b['block_number']) for a,b in zip(states,states[1:])]
 unique={(r['event'],r['asset'],r['unix']):r for r in prices};prices=sorted(unique.values(),key=lambda r:(r['event'],r['asset'],r['unix']))
 (OUT/'prices_hourly.json').write_text(json.dumps(prices,separators=(',',':')))
 (OUT/'gas_headers.json').write_text(json.dumps(headers,separators=(',',':')))
 logs=[];failures=[]
 with ThreadPoolExecutor(max_workers=4) as ex:
  futures={ex.submit(interval,j):j for j in jobs}
  for i,f in enumerate(as_completed(futures),1):
   try:r=f.result();logs.extend({**x,'collection_event':r['event']} for x in r['logs'])
   except Exception as e:failures.append(dict(job=futures[f],error=str(e)));print('FAILED',failures[-1],flush=True)
   if i%12==0:print('LOG INTERVALS',i,'/',len(jobs),'events',len(logs),'failures',len(failures),flush=True)
 (OUT/'failed_intervals.json').write_text(json.dumps(failures,indent=2))
 if failures:raise ValueError('Incomplete intervals retained; rerun to resume')
 source_path=ROOT/'empirical_data/pool_events.json'
 svb_bytes=source_path.read_bytes() if source_path.exists() else gzip.decompress(source_path.with_suffix('.json.gz').read_bytes())
 svb=json.loads(svb_bytes);low=groups['SVB_2023_03'][0]['block_number'];high=groups['SVB_2023_03'][-1]['block_number']
 logs += [{**r,'collection_event':'SVB_2023_03'} for r in svb if low<int(r['blockNumber'],16)<=high]
 logs=sorted({(r['transactionHash'],r['logIndex']):r for r in logs}.values(),key=lambda r:(int(r['blockNumber'],16),int(r['logIndex'],16)))
 with gzip.open(OUT/'pool_events.json.gz','wt') as f:json.dump(logs,f,separators=(',',':'))
 # Small independent receipt checks, two spread-out swaps per event.
 checks=[]
 for event in groups:
  es=[e for e in logs if e['collection_event']==event and e['topics'][0].lower()==TOPICS[0].lower()]
  for index in [len(es)//3,2*len(es)//3]:
   e=es[index];receipt=rpc('eth_getTransactionReceipt',[e['transactionHash']]);match=next((l for l in receipt['logs'] if l['logIndex']==e['logIndex']),None)
   passed=bool(match and match['data']==e['data'] and match['topics']==e['topics'] and receipt['blockHash']==e['blockHash'])
   if not passed:raise ValueError('Receipt mismatch')
   checks.append(dict(event=event,transaction_hash=e['transactionHash'],log_index=e['logIndex'],block_number=int(e['blockNumber'],16),passed=passed))
 (OUT/'receipt_checks.json').write_text(json.dumps(checks,indent=2))
 # Sharded raw archive: each gzip below browser upload limits.
 paths=sorted(RAW.glob('*.json'));shards=[]
 for start in range(0,len(paths),400):
  name=f'raw_responses_{start//400:02d}.jsonl.gz'
  with gzip.open(OUT/name,'wt') as f:
   for p in paths[start:start+400]:f.write(p.read_text()+'\n')
  shards.append(name)
 meta=dict(generated_at_utc=utc(time.time()),new_price_observations=sum(r['source_kind'].startswith('newly') for r in prices),all_price_observations=len(prices),gas_header_count=len(headers),pool_events=len(logs),events={e:sum(r['collection_event']==e for r in logs) for e in groups},completed_log_intervals=len(jobs),failed_intervals=0,raw_shards=shards,raw_response_count=len(paths),svb_reused_source_sha256=hashlib.sha256(svb_bytes).hexdigest(),svb_price_source_sha256=hashlib.sha256((ROOT/'empirical_data/prices_hourly.json').read_bytes()).hexdigest(),state_source_sha256=hashlib.sha256((ROOT/'archive_extension/unique_pool_states.json').read_bytes()).hexdigest(),protocol_sha256=hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest())
 (OUT/'collection_manifest.json').write_text(json.dumps(meta,indent=2));print('COLLECTION COMPLETE',json.dumps(meta),flush=True)
if __name__=='__main__':main()
