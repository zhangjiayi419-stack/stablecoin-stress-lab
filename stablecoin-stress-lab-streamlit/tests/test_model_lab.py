"""Chronology and comparable evaluation checks."""
import sys,unittest
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model_lab import predict,evaluate,fingerprint,saved_chronos,origins


def data():
    return [dict(asset=a,date_utc=(date(2024,1,1)+timedelta(days=i)).isoformat(),close_usd=1+((i%7)-3)*.0001) for a in ('USDC','USDT') for i in range(60)]

class ModelLabChecks(unittest.TestCase):
    def test_shared_origins_and_targets(self):
        for horizon in (1,3,7):
            r=evaluate(data(),'USDC',horizon)
            grouped={m:{(x['origin'],x['target']) for x in r['predictions'] if x['model']==m} for m in {s['model'] for s in r['scores']}}
            self.assertTrue(all(v==next(iter(grouped.values())) for v in grouped.values()))
            self.assertEqual(len(r['projections']),4*horizon)
            self.assertEqual(r['scores'][0]['stress_n'],0)
    def test_future_change_cannot_change_earlier_prediction(self):
        original=data();changed=data()
        for row in changed:
            if row['date_utc']>='2024-02-25':row['close_usd']=.9
        a=evaluate(original,'USDC',1);b=evaluate(changed,'USDC',1)
        aa=[r['prediction_usd'] for r in a['predictions'] if r['origin']<'2024-02-25']
        bb=[r['prediction_usd'] for r in b['predictions'] if r['origin']<'2024-02-25']
        self.assertEqual(aa,bb)
    def test_constant_series_and_zero_baseline_error(self):
        rows=data()
        for row in rows:row['close_usd']=1.
        r=evaluate(rows,'USDC',7)
        self.assertTrue(all(s['mae_bps']==0 and s['improvement_pct'] is None for s in r['scores']))
    def test_hash_ignores_order_and_changes_with_values(self):
        rows=data();self.assertEqual(fingerprint(rows),fingerprint(list(reversed(rows))))
        rows[0]['close_usd']=.9;self.assertNotEqual(fingerprint(rows),fingerprint(data()))
        self.assertIsNone(saved_chronos(rows))
    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):evaluate(data()[:-10]+data()[-9:],'USDT',1)
        with self.assertRaises(ValueError):predict([1.]*30,'AR(1)',2)

if __name__=='__main__':unittest.main()
