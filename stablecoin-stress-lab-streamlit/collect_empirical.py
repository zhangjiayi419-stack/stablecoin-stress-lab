"""Resumable public-data collection. No credentials, ≤4 workers, raw responses retained."""
import json,hashlib,time,threading
from pathlib import Path
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
import requests
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'empirical_data';RAW=OUT/'raw';RAW.mkdir(parents=True,exist_ok=True)
POOL='0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7';RPC='https://eth.drpc.org'
TLS=threading.local()
LOG_LOCK=threading.Lock()
LAST_LOG_REQUEST=0.

def session():
    if not hasattr(TLS,'session'):TLS.session=requests.Session()
    return TLS.session

def fetch(url,payload=None):
    key=hashlib.sha256(json.dumps([url,payload],sort_keys=True).encode()).hexdigest()
    path=RAW/(key+'.json')
    if path.exists():return json.loads(path.read_text())['response']
    for attempt in range(3):
        try:
            if 'blockscout.com' in url:
                global LAST_LOG_REQUEST
                with LOG_LOCK:
                    time.sleep(max(0,1.0-(time.monotonic()-LAST_LOG_REQUEST)))
                    LAST_LOG_REQUEST=time.monotonic()
            r=session().get(url,timeout=45) if payload is None else session().post(url,json=payload,timeout=45)
            if r.status_code==429:
                time.sleep(min(30,float(r.headers.get('Retry-After',5*(attempt+1)))))
            r.raise_for_status();data=r.json()
            if isinstance(data,dict) and 'error' in data:raise ValueError(str(data['error']))
            if isinstance(data,list) and any('error' in x for x in data):raise ValueError(str([x for x in data if 'error' in x]))
            doc=dict(url=url,request=payload,retrieved_at_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),response=data)
            path.write_text(json.dumps(doc,separators=(',',':')))
            return data
        except (requests.RequestException,ValueError):
            if attempt==2:raise
            time.sleep(1+attempt*2)

def rpc(method,params):
    return fetch(RPC,dict(jsonrpc='2.0',id=1,method=method,params=params))['result']

def calls(block,datas):
    req=[dict(jsonrpc='2.0',id=i,method='eth_call',params=[dict(to=POOL,data=data),hex(block)]) for i,data in enumerate(datas)]
    responses=[]
    for start in range(0,len(req),2):responses.extend(fetch(RPC,req[start:start+2]))
    return [int(x['result'],16) for x in sorted(responses,key=lambda r:r['id'])]

def encode(selector,*args):return selector+''.join(f'{a:064x}' for a in args)

def utc(ts):return datetime.fromtimestamp(ts,timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')

def block_at(ts):
    item=fetch('https://coins.llama.fi/block/ethereum/'+str(ts));block=item['height']
    header=rpc('eth_getBlockByNumber',[hex(block),False])
    while int(header['timestamp'],16)>ts:
        block-=1;header=rpc('eth_getBlockByNumber',[hex(block),False])
    return block,header

def snapshot(ts):
    path=OUT/'snapshots'/f'{ts}.json';path.parent.mkdir(exist_ok=True)
    if path.exists():return json.loads(path.read_text())
    block,h=block_at(ts)
    vals=calls(block,[encode('0x4903b0d1',i) for i in range(3)]+['0xf446c1d0','0xddca3f43',encode('0x5e0d443f',1,2,10**12)])
    result=dict(cutoff_utc=utc(ts),timestamp=utc(int(h['timestamp'],16)),block_number=block,block_hash=h['hash'],
        raw_balances=vals[:3],dai_pool=vals[0]/1e18,usdc_pool=vals[1]/1e6,usdt_pool=vals[2]/1e6,
        amp=vals[3],fee_rate=vals[4]/1e10,contract_quote_1m_usdc_to_usdt=vals[5]/1e6,
        source=RPC,contract=POOL)
    path.write_text(json.dumps(result));return result

def prices():
    rows=[]
    start=int(datetime(2023,1,1,tzinfo=timezone.utc).timestamp())
    for offset in range(0,105*24,6*24):
        ts=start+offset*3600
        url=f'https://coins.llama.fi/chart/coingecko:usd-coin,coingecko:tether,coingecko:dai?start={ts}&span={min(144,105*24-offset)}&period=1h&searchWidth=30m'
        data=fetch(url)
        for coin,info in data['coins'].items():
            for p in info['prices']:
                rows.append(dict(timestamp=utc(p['timestamp']),unix=p['timestamp'],asset={'coingecko:usd-coin':'USDC','coingecko:tether':'USDT','coingecko:dai':'DAI'}[coin],price_usd=p['price'],source=url))
        print('Price week',offset//144+1,flush=True)
    unique={(r['asset'],r['unix']):r for r in rows};rows=sorted(unique.values(),key=lambda r:(r['asset'],r['unix']))
    (OUT/'prices_hourly.json').write_text(json.dumps(rows,separators=(',',':')))
    return rows

def logs_for(pair):
    from eth_hash.auto import keccak
    left,right=pair
    path=OUT/'logs_rpc'/f'{left}-{right}.json';path.parent.mkdir(exist_ok=True)
    if path.exists():return json.loads(path.read_text())
    signatures=['TokenExchange(address,int128,uint256,int128,uint256)','AddLiquidity(address,uint256[3],uint256[3],uint256,uint256)','RemoveLiquidity(address,uint256[3],uint256[3],uint256)','RemoveLiquidityOne(address,uint256,uint256)','RemoveLiquidityImbalance(address,uint256[3],uint256[3],uint256,uint256)']
    topics=['0x'+keccak(x.encode()).hex() for x in signatures]
    result=[]
    # Provider free-tier requests are kept within 100 blocks; every subrange is retained.
    for start in range(left,right+1,100):
        part=rpc('eth_getLogs',[dict(address=POOL,fromBlock=hex(start),toBlock=hex(min(start+99,right)),topics=[topics])])
        if len(part)>=1000:raise ValueError('Log result cap reached; reduce block size.')
        result.extend(part)
    if any(x.get('removed') for x in result):raise ValueError('Removed log in historical range')
    path.write_text(json.dumps(result,separators=(',',':')));return result

def main():
    prices()
    start=datetime(2023,1,1,tzinfo=timezone.utc)
    daily=[int((start+timedelta(days=i+1)).timestamp())-1 for i in range(105)]
    crisis=datetime(2023,3,7,tzinfo=timezone.utc)
    hourly=[int((crisis+timedelta(hours=i)).timestamp()) for i in range(10*24+1)]
    targets=sorted(set(daily+hourly));results=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for i,r in enumerate(ex.map(snapshot,targets)):
            results.append(r)
            if i%20==0:print('Snapshots',i+1,'/',len(targets),flush=True)
    (OUT/'pool_states.json').write_text(json.dumps(results,separators=(',',':')))
    hs=sorted([r for r in results if r['cutoff_utc'] in {utc(t) for t in hourly}],key=lambda r:r['block_number'])
    pairs=[(hs[i]['block_number']+1,hs[i+1]['block_number']) for i in range(len(hs)-1)]
    logs=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for i,r in enumerate(ex.map(logs_for,pairs)):
            logs.extend(r)
            if i%20==0:print('Log intervals',i+1,'/',len(pairs),'events',len(logs),flush=True)
    unique={(r['transactionHash'],r['logIndex']):r for r in logs}
    (OUT/'pool_events.json').write_text(json.dumps(list(unique.values()),separators=(',',':')))
    print('COLLECTION COMPLETE',len(results),'states',len(unique),'events',flush=True)

if __name__=='__main__':main()
