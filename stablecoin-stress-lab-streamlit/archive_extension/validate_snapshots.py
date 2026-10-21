"""Independent offline checks of collected state and cutoff alignment."""
import json,math,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent

def main():
    rows=json.loads((ROOT/'cutoff_observations.json').read_text())
    prior={r['block_number']:r for r in json.loads((ROOT/'prior_346_states.json').read_text())}
    issues=[];overlap=0;raw_count=0
    for row in rows:
        if not row['timestamp']<=row['requested_cutoff_utc']<row['next_block_timestamp']:issues.append([row['block_number'],'cutoff_alignment'])
        if len(row['block_hash'])!=66 or not row['block_hash'].startswith('0x'):issues.append([row['block_number'],'hash_format'])
        if not all(math.isfinite(row[k]) and row[k]>0 for k in ['dai_pool','usdc_pool','usdt_pool','amp','contract_quote_1m_usdc_to_usdt']):issues.append([row['block_number'],'invalid_numeric_state'])
        observed_calls={}
        for name in row['raw_response_files']:
            path=ROOT/'raw_responses'/name
            if not path.exists():issues.append([row['block_number'],'missing_raw_response'])
            else:
                raw_count+=1;doc=json.loads(path.read_text())
                if isinstance(doc.get('request'),list):
                    requests_by_id={q['id']:q for q in doc['request']}
                    for answer in doc['response']:
                        request=requests_by_id[answer['id']]
                        if request['method']=='eth_call':
                            if request['params'][1]!=hex(row['block_number']):issues.append([row['block_number'],'raw_call_wrong_block'])
                            observed_calls[answer['id']]=int(answer['result'],16)
        expected=[int(row['raw_dai_balance']),int(row['raw_usdc_balance']),int(row['raw_usdt_balance']),row['amp'],round(row['fee_rate']*1e10),round(row['contract_quote_1m_usdc_to_usdt']*1e6)]
        if any(observed_calls.get(i)!=v for i,v in enumerate(expected)):issues.append([row['block_number'],'raw_state_mismatch'])
        if row['block_number'] in prior:
            overlap+=1;old=prior[row['block_number']]
            if old['block_hash']!=row['block_hash']:issues.append([row['block_number'],'prior_block_hash_mismatch'])
            for k in ['dai_pool','usdc_pool','usdt_pool','amp','fee_rate']:
                if not math.isclose(float(old[k]),float(row[k]),rel_tol=1e-12,abs_tol=1e-10):issues.append([row['block_number'],'prior_state_mismatch',k])
    unique=json.loads((ROOT/'unique_pool_states.json').read_text())
    if len(unique)!=len({r['block_number'] for r in unique}):issues.append(['deduplication'])
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for name,expected in manifest['files'].items():
        path=ROOT/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:issues.append(['sha256_mismatch',name])
    report=dict(validated_at_utc=datetime.now(timezone.utc).isoformat(),cutoff_rows_checked=len(rows),unique_blocks_checked=len(unique),prior_346_overlap_rows_checked=overlap,raw_response_references_checked=raw_count,issues=issues,passed=not issues,maximum_solver_relative_error_bps=max(abs(r['solver_relative_error_bps']) for r in rows))
    (ROOT/'validation_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    if issues:raise SystemExit(1)
if __name__=='__main__':main()
