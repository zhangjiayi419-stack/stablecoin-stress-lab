import gzip,json,math,unittest,hashlib
from pathlib import Path
from datetime import datetime
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'cross_event_study'
def load(n):return json.loads((DATA/n).read_text())
def ts(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()

class CrossEventTests(unittest.TestCase):
    def test_source_alignment_and_full_intervals(self):
        rows=load('microstructure_features.json');headers={r['block_number']:r for r in load('gas_headers.json')}
        meta=load('collection_manifest.json')
        self.assertEqual(meta['failed_intervals'],0)
        self.assertTrue(all(c['passed'] for c in load('receipt_checks.json')))
        with gzip.open(DATA/'pool_events.json.gz','rt') as f:logs=json.load(f)
        identities={(r['transactionHash'],r['logIndex']) for r in logs}
        self.assertEqual(len(identities),len(logs))
        for r in rows:
            self.assertLessEqual(ts(r['state_utc']),ts(r['cutoff_utc']))
            self.assertLessEqual(r['source_interval_from_block'],r['source_interval_to_block'])
            self.assertEqual(r['block_hash'],headers[r['block_number']]['block_hash'])
            self.assertEqual(r['base_fee_gwei'],headers[r['block_number']]['base_fee_gwei'])
            for asset in ['dai','usdc','usdt']:
                age=ts(r['cutoff_utc'])-ts(r['price_'+asset+'_observed_at'])
                self.assertTrue(0<=age<=7200)
        self.assertEqual(len(rows),sum(r['aligned_intervals'] for r in load('coverage.json')))

    def test_forward_chronology_shared_targets_and_scores(self):
        result=load('results.json');p=load('protocol.json')
        self.assertEqual(len(result['folds']),4)
        self.assertEqual(p['gb_settings']['random_state'],419)
        for fold in result['folds']:
            self.assertLess(fold['calibration_end'],fold['test_start'])
            self.assertNotIn(fold['test_event'],fold['train_events'])
            common=[]
            for score in fold['scores']:
                rows=[r for r in fold['predictions'] if r['model']==score['Model']]
                common.append({(r['origin'],r['target']) for r in rows})
                self.assertTrue(all(ts(r['target'])-ts(r['origin'])==3600 for r in rows))
                self.assertTrue(all(ts(r['origin'])<ts(r['target_price_observed_at'])<=ts(r['target']) for r in rows))
                errors=[abs(r['prediction_bps']-r['actual_bps']) for r in rows]
                self.assertEqual(len(rows),score['Targets'])
                self.assertAlmostEqual(sum(errors)/len(errors),score['MAE_bps'])
                self.assertAlmostEqual(math.sqrt(sum(e*e for e in errors)/len(errors)),score['RMSE_bps'])
                self.assertLessEqual(score['MAE_bps'],score['RMSE_bps']+1e-10)
                self.assertLessEqual(score['RMSE_bps'],score['Max_error_bps']+1e-10)
                self.assertEqual(score['Stress_targets'],sum(r['stress'] for r in rows))
            self.assertTrue(all(s==common[0] for s in common))

    def test_frozen_intervals_reconstruct_from_preevent_residuals(self):
        for fold in load('results.json')['folds']:
            for model,radius in fold['calibration_radius_bps'].items():
                cal=[r for r in fold['calibration_predictions'] if r['model']==model]
                self.assertEqual(len(cal),32)
                self.assertTrue(all(r['target']<fold['test_start'] for r in cal))
                residuals=sorted(abs(r['actual_bps']-r['prediction_bps']) for r in cal)
                self.assertAlmostEqual(radius,residuals[math.ceil(33*.9)-1])
                for r in [r for r in fold['predictions'] if r['model']==model]:
                    self.assertAlmostEqual(r['upper_bps']-r['prediction_bps'],radius)
                    self.assertAlmostEqual(r['prediction_bps']-r['lower_bps'],radius)

    def test_ui_switches_test_event_and_asset_without_errors(self):
        app=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=30).run()
        app.radio(key='workspace').set_value('Forecast Lab').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key='transfer_event').value,'FTX_2022_11')
        app.selectbox(key='transfer_event').set_value('SVB_2023_03').run()
        app.selectbox(key='transfer_asset').set_value('USDT').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Retrospective event transfer' in r.value for r in app.warning))
        app.radio(key='workspace').set_value('Data & Contract Evidence').run()
        self.assertFalse(app.exception)
        app.radio(key='workspace').set_value('Forecast Lab').run()
        self.assertEqual(app.selectbox(key='transfer_event').value,'SVB_2023_03')
        self.assertEqual(app.selectbox(key='transfer_asset').value,'USDT')
        self.assertFalse(app.exception)


class RawMeasurementAudit(unittest.TestCase):
    def test_swap_volume_and_gas_reconcile_with_raw_responses(self):
        with gzip.open(DATA/'pool_events.json.gz','rt') as f:logs=json.load(f)
        from collect_cross_event import TOPICS
        prices=load('prices_hourly.json');features=load('microstructure_features.json')
        raw_headers={}
        for name in load('collection_manifest.json')['raw_shards']:
            with gzip.open(DATA/name,'rt') as f:
                for line in f:
                    d=json.loads(line);request=d['request']
                    if isinstance(request,dict) and request.get('method')=='eth_getBlockByNumber':
                        raw_headers[int(request['params'][0],16)]=d['response']['result']
        for event in ['Terra_2022_05','FTX_2022_11','SVB_2023_03']:
            rs=[r for r in features if r['event']==event];r=rs[len(rs)//2]
            observed={a:max((p for p in prices if p['event']==event and p['asset']==a and ts(p['timestamp'])<=ts(r['cutoff_utc'])),key=lambda p:p['unix'])['price_usd'] for a in ['DAI','USDC','USDT']}
            swaps=[e for e in logs if r['source_interval_from_block']<=int(e['blockNumber'],16)<=r['source_interval_to_block'] and e['topics'][0].lower()==TOPICS[0].lower()]
            volume=0.
            for e in swaps:
                coin=int(e['data'][2:66],16);raw=int(e['data'][66:130],16)
                volume+=raw/[1e18,1e6,1e6][coin]*observed[['DAI','USDC','USDT'][coin]]
            self.assertAlmostEqual(volume,r['swap_volume_usd'],places=5)
            self.assertEqual(int(raw_headers[r['block_number']]['baseFeePerGas'],16)/1e9,r['base_fee_gwei'])
            self.assertEqual(raw_headers[r['block_number']]['hash'],r['block_hash'])

if __name__=='__main__':unittest.main()
