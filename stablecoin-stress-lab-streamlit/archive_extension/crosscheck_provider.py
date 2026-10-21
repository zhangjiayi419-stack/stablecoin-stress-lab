"""Cross-check two fixed blocks per event with a second public archive RPC."""
import json,time
from pathlib import Path
from datetime import datetime,timezone
import requests
ROOT=Path(__file__).resolve().parent
RPC='https://eth-mainnet.public.blastapi.io'
def main():
    rows=json.loads((ROOT/'unique_pool_states.json').read_text());checks=[]
    for event in ['Terra_2022_05','FTX_2022_11','SVB_2023_03']:
        group=[r for r in rows if event in r['events']]
        for r in [group[len(group)//3],group[2*len(group)//3]]:
            payload=[dict(jsonrpc='2.0',id=0,method='eth_getBlockByNumber',params=[hex(r['block_number']),False]),dict(jsonrpc='2.0',id=1,method='eth_call',params=[dict(to=r['contract'],data='0x5e0d443f'+''.join(f'{a:064x}' for a in [1,2,10**12])),hex(r['block_number'])])]
            item=dict(event=event,block_number=r['block_number'],source=RPC,request=payload,retrieved_at_utc=datetime.now(timezone.utc).isoformat())
            try:
                response=requests.post(RPC,json=payload,timeout=30);response.raise_for_status();data=response.json();item['response']=data
                by_id={v['id']:v for v in data};item['block_hash_match']=by_id[0]['result']['hash']==r['block_hash'];item['quote_match']=int(by_id[1]['result'],16)/1e6==r['contract_quote_1m_usdc_to_usdt'];item['passed']=item['block_hash_match'] and item['quote_match']
            except Exception as err:item.update(passed=False,error=str(err))
            checks.append(item);print(event,r['block_number'],item['passed'],flush=True);time.sleep(.2)
    (ROOT/'independent_provider_crosschecks.json').write_text(json.dumps(checks,indent=2))
if __name__=='__main__':main()
