"""Offline inference only. Install requirements-research.txt; publish JSON, not weights."""
import json
import os
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
os.environ.setdefault('HF_HOME',str(ROOT.parent/'model-cache'))
os.environ.setdefault('HF_HUB_DISABLE_XET','1')
import torch
import importlib.metadata
from huggingface_hub import model_info
from chronos import Chronos2Pipeline
from forecast_brief import clean_series
from model_lab import fingerprint,origins


def build():
    torch.set_num_threads(2);torch.manual_seed(419)
    rows=json.loads((ROOT/'reports/prices_latest.json').read_text())
    revision=model_info('amazon/chronos-2').sha
    print('Loading amazon/chronos-2 revision',revision,flush=True)
    pipeline=Chronos2Pipeline.from_pretrained('amazon/chronos-2',revision=revision,device_map='cpu',dtype=torch.float32)
    inputs=[];labels=[]
    for asset in ('USDC','USDT'):
        items=clean_series(rows,asset);values=[(v-1)*10000 for _,v in items]
        for i in origins(len(items)):
            inputs.append(torch.tensor(values[:i],dtype=torch.float32));labels.append((asset,items[i-1][0].isoformat(),'test'))
        inputs.append(torch.tensor(values,dtype=torch.float32));labels.append((asset,items[-1][0].isoformat(),'forecast'))
    print('Inference contexts:',len(inputs),'· cross_learning=False · peg deviations in bps',flush=True)
    quantiles,_=pipeline.predict_quantiles(inputs,prediction_length=7,quantile_levels=[.1,.5,.9],batch_size=8,cross_learning=False)
    result=dict(dataset_sha256=fingerprint(rows),metadata=dict(model_id='amazon/chronos-2',revision=revision,
        chronos_version=importlib.metadata.version('chronos-forecasting'),torch_version=torch.__version__,generated_at_utc=datetime.now(timezone.utc).isoformat(),
        device='CPU float32',target='USD-peg deviation in bps, inverse transformed to USD',context='Univariate; no cross-origin or cross-asset learning',
        seed=419,pretraining_overlap='Not independently audited; chronology applies to inference inputs only.',
        refresh='Offline artifact; hidden automatically if the evaluated dataset hash changes.'),backtests={'USDC':{},'USDT':{}},forecast={})
    for (asset,origin,kind),q in zip(labels,quantiles):
        array=q[0].detach().cpu().tolist();median=[1+r[1]/10000 for r in array]
        if kind=='test':result['backtests'][asset][origin]=median
        else:result['forecast'][asset]=dict(as_of=origin,median=median,lower_80=[1+r[0]/10000 for r in array],upper_80=[1+r[2]/10000 for r in array])
    (ROOT/'chronos_snapshot.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    print('Saved real Chronos-2 inference artifact',flush=True)

if __name__=='__main__':build()
