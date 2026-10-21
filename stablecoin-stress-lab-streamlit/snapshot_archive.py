"""Versioned multi-event block archive. Does not replace frozen simulation anchors."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ARCHIVE=ROOT/'archive_extension'
EVENTS={'SVB · March 2023':'SVB_2023_03','Terra · May 2022':'Terra_2022_05','FTX · November 2022':'FTX_2022_11'}

def load_archive():
    rows=json.loads((ARCHIVE/'unique_pool_states.json').read_text())
    manifest=json.loads((ARCHIVE/'manifest.json').read_text())
    expected=manifest['files']['unique_pool_states.json']
    if hashlib.sha256((ARCHIVE/'unique_pool_states.json').read_bytes()).hexdigest()!=expected:raise ValueError('Archive fingerprint mismatch')
    if len(rows)!=manifest['unique_blocks'] or len({(r['chain_id'],r['contract'],r['block_number']) for r in rows})!=len(rows):raise ValueError('Archive count or block identity mismatch')
    return rows,manifest

def event_rows(rows,event,date=None):
    return sorted([r for r in rows if event in r['events'] and (date is None or r['requested_cutoff_utc'][:10]==date)],key=lambda r:r['block_number'])

def execution(snapshot,amount,input_index=1,output_index=2):
    from backend.app.domain.stable_swap import quote_swap
    if input_index==output_index:raise ValueError('Choose different tokens')
    return quote_swap(snapshot,input_index,output_index,amount)
