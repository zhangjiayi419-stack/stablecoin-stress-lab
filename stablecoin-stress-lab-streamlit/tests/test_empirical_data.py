"""Checks on the collected immutable evidence package, not desired model rankings."""
import sys,json,unittest,math
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from econometrics import digest
ROOT=Path(__file__).resolve().parents[1]/'empirical_data'

class CollectedEvidenceChecks(unittest.TestCase):
    def load(self,name):return json.loads((ROOT/name).read_text())
    def test_state_and_price_clocks(self):
        for r in self.load('pool_states.json'):
            self.assertLessEqual(r['timestamp'],r['cutoff_utc'])
            self.assertTrue(all(r[k]>0 for k in ['dai_pool','usdc_pool','usdt_pool']))
        f=self.load('microstructure_features.json')
        self.assertGreaterEqual(len(f),200)
        for r in f:
            self.assertLessEqual(r['price_usdc_observed_at'],r['cutoff_utc'])
            self.assertLessEqual(r['price_usdt_observed_at'],r['cutoff_utc'])
            self.assertEqual(r['source_interval_to_block'],r['block_number'])
            self.assertTrue(math.isfinite(r['volume_spike']))
        for a,b in zip(f,f[1:]):
            self.assertGreaterEqual((datetime.fromisoformat(b['cutoff_utc'])-datetime.fromisoformat(a['cutoff_utc'])).total_seconds(),3600)
    def test_real_contract_benchmarks(self):
        rows=self.load('contract_benchmarks.json')
        self.assertEqual(len(rows),30);self.assertEqual(len({r['block_number'] for r in rows}),5)
        for r in rows:
            self.assertEqual(r['contract_output_tokens'],int(r['contract_output_raw'])/1e6)
            self.assertAlmostEqual(r['relative_error_bps'],(r['python_output_tokens']/r['contract_output_tokens']-1)*10000,places=9)
            self.assertTrue(math.isfinite(r['relative_error_bps']))
        self.assertTrue(all(r['rpc_receipt_match'] for r in self.load('event_crosschecks.json')))
    def test_feature_hash_and_common_covariate_targets(self):
        data=self.load('microstructure_features.json');result=self.load('covariate_results.json')
        self.assertEqual(digest(data),result['feature_sha256'])
        for value in result['results'].values():
            for r in value['predictions']:
                self.assertEqual((datetime.fromisoformat(r['target'])-datetime.fromisoformat(r['origin'])).total_seconds(),3600)
            groups=[{r['target'] for r in value['predictions'] if r['model']==m} for m in ['Persistence','GB price-only','GB + observed covariates']]
            self.assertTrue(all(g==groups[0] for g in groups))
    def test_svb_has_real_usdc_stress(self):
        results=self.load('econometric_results.json')['results']
        for h in [1,3,7]:
            r=results[f'svb|USDC|{h}|Bounded ACI']
            self.assertTrue(all(s['Stress_targets']>0 for s in r['scores']))
            origins=[{p['origin'] for p in r['predictions'] if p['model']==m} for m in ['Persistence','SETAR','Gradient boosting']]
            self.assertEqual(origins[0],origins[1]);self.assertEqual(origins[1],origins[2])

if __name__=='__main__':unittest.main()
