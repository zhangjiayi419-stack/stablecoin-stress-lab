import json
from pathlib import Path
from model_lab import evaluate,saved_chronos,fingerprint,VERSION
rows=json.load(open('reports/prices_latest.json'));artifact=saved_chronos(rows)
results={}
for asset in ['USDC','USDT']:
 for h in [1,3,7]:
  results[asset+'|'+str(h)]=evaluate(rows,asset,h,artifact)
  print(asset,h,flush=True)
Path('foundation_evaluations.json').write_text(json.dumps(dict(version=VERSION,dataset_sha256=fingerprint(rows),results=results),separators=(',',':')))
