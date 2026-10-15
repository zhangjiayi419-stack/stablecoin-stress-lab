"""Presentation data: keep observed prices, historical execution and scenarios separate."""
import json
from datetime import date, datetime, timezone
from pathlib import Path
import pandas as pd
from backend.app.services.replay import load_history, load_pool_state

ROOT = Path(__file__).resolve().parent
TOKEN_COLORS = {'USDC':'#2268c8','USDT':'#13816d','DAI':'#b58a31'}
CASES = {
    'USDC · March 2023': ('2023-03-09','2023-03-15','2023-03-11','EVT-2023-03-10-svb'),
    'USDT · May 2022': ('2022-05-08','2022-05-16','2022-05-12','EVT-2022-05-09-terra-luna'),
    'USDT · November 2022': ('2022-11-06','2022-11-15','2022-11-09','EVT-2022-11-08-ftx'),
}

def load_research():
    history = load_history()
    frame = pd.DataFrame(history['prices'])
    for column in ('close_usd','mean_usd','min_sampled_usd','max_sampled_usd'):
        frame[column] = pd.to_numeric(frame[column],errors='coerce')
    return history, frame, load_pool_state()


def latest_market(history):
    path = ROOT/'reports/prices_latest.json'
    rows = json.loads(path.read_text()) if path.exists() else history['prices']
    frame = pd.DataFrame(rows)
    frame['close_usd'] = pd.to_numeric(frame['close_usd'],errors='raise')
    dates = [set(frame.loc[frame.asset==asset,'date_utc']) for asset in ('USDC','USDT')]
    shared = sorted(set.intersection(*dates))
    if not shared:
        raise ValueError('No shared USD observation date is available.')
    as_of = shared[-1]
    age = (datetime.now(timezone.utc).date()-date.fromisoformat(as_of)).days
    return rows, frame, as_of, age


def saved_report():
    path = ROOT/'reports/latest.json'
    return json.loads(path.read_text()) if path.exists() else None


def event_frames(frame, snapshots, case):
    start, end, selected, event_id = CASES[case]
    prices = frame[frame.date_utc.between(start,end)].copy()
    pools = [s for s in snapshots if start <= s['timestamp'][:10] <= end]
    shares=[]
    for snapshot in pools:
        total = sum(float(snapshot[k]) for k in ('dai_pool','usdc_pool','usdt_pool'))
        for asset in ('DAI','USDC','USDT'):
            amount = float(snapshot[asset.lower()+'_pool'])
            shares.append(dict(date_utc=snapshot['timestamp'][:10],asset=asset,share_pct=amount/total*100,tokens=amount))
    return prices,pools,pd.DataFrame(shares)


def snapshot_detail(snapshot):
    return {'UTC block time':snapshot['timestamp'], 'Source':snapshot['source'],
            'Method':snapshot['method'], 'Curve A':float(snapshot['amp']),
            'Swap fee (bps)':float(snapshot['fee_rate'])*10000}
