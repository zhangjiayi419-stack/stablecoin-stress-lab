"""Session-scoped experiment records, no shared visitor storage."""
from pathlib import Path
import hashlib
import json
from datetime import datetime,timezone
import streamlit as st
import pandas as pd


def record(kind,request,result):
    payload=json.loads(json.dumps(dict(kind=kind,request=request,result=result),default=str))
    run_id=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:12]
    records=st.session_state.setdefault('experiment_journal',[])
    if not any(r['run_id']==run_id for r in records):
        records.append(dict(run_id=run_id,created_at_utc=datetime.now(timezone.utc).isoformat(),**payload))
        del records[:-20]
    return run_id


def render_journal():
    st.markdown('<div class="eyebrow">08 / Reproducible research</div>',unsafe_allow_html=True)
    st.title('Experiment Journal')
    st.write('Inspect the inputs, outputs and timestamps behind your research runs.')
    st.caption('Three read-only canonical benchmarks are preloaded from executed runs. Your latest 20 distinct session runs are added separately and are not shared with other visitors. Download the journal to retain session work.')
    path=Path(__file__).with_name('canonical_benchmarks.json')
    canonical=json.loads(path.read_text()) if path.exists() else []
    records=canonical+st.session_state.get('experiment_journal',[])
    if not records:
        st.info('Run a Forecast Lab comparison, liquidity experiment, holdings scenario or connected mechanism test to create a record.')
        return
    st.dataframe(pd.DataFrame([dict(run_id=r['run_id'],experiment=r['kind'],created_at_utc=r['created_at_utc']) for r in reversed(records)]),hide_index=True,width='stretch')
    selected=st.selectbox('Inspect run',list(reversed(records)),format_func=lambda r:r['kind']+' · '+r['run_id'])
    a,b=st.tabs(['Submitted assumptions','Recorded output'])
    with a:
        st.json(selected['request'])
        if selected.get('metadata'):st.json(selected['metadata'])
    with b:st.json(selected['result'])
    st.download_button('Download selected run',json.dumps(selected,indent=2),selected['run_id']+'.json','application/json')
    st.download_button('Download session journal',json.dumps(records,indent=2),'research-journal.json','application/json')
