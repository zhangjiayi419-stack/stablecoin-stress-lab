"""Restore saved raw JSONL to the request-keyed cache; no network requests."""
import gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
raw=ROOT/'raw_responses';raw.mkdir(exist_ok=True)
n=0
with gzip.open(ROOT/'raw_responses.jsonl.gz','rt') as f:
    for line in f:
        doc=json.loads(line)
        key=hashlib.sha256(json.dumps([doc['url'],doc.get('request')],sort_keys=True).encode()).hexdigest()
        (raw/(key+'.json')).write_text(json.dumps(doc,separators=(',',':')));n+=1
print('Restored',n,'raw response documents; no network calls.')
