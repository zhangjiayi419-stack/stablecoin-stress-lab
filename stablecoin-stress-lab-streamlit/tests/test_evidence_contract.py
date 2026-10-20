import json,unittest,math
from pathlib import Path
from home_ui import findings
from participant_comparison import pressure_audit,request_fingerprint
from backend.app.domain.schemas import AgentExperimentRequest
from backend.app.services.agents import simulate_agents
ROOT=Path(__file__).resolve().parents[1]

class EvidenceContract(unittest.TestCase):
    def test_home_distinguishes_ablation_and_baseline(self):
        f=findings()
        self.assertEqual(f['stress_targets'],1)
        self.assertGreater(f['ablation_gain'],0)
        self.assertLess(f['covariate_improvement'],0)
        self.assertLess(f['price_only_improvement'],f['covariate_improvement'])

    def test_retrospective_audit_has_shared_chronological_targets(self):
        data=json.loads((ROOT/'empirical_data/event_audit.json').read_text())
        self.assertEqual(len(data['events']),3)
        for event in data['events']:
            groups=[]
            for score in event['scores']:
                rs=[r for r in event['predictions'] if r['model']==score['Model']]
                groups.append({r['target'] for r in rs})
                self.assertTrue(all(r['origin']<r['target'] and event['start']<=r['target']<=event['end'] for r in rs))
                mae=sum(r['abs_error_bps'] for r in rs)/len(rs)
                rmse=math.sqrt(sum(r['abs_error_bps']**2 for r in rs)/len(rs))
                self.assertAlmostEqual(score['MAE_bps'],mae)
                self.assertAlmostEqual(score['RMSE_bps'],rmse)
                self.assertLessEqual(score['RMSE_bps'],score['Max_error_bps']+1e-10)
                self.assertEqual(score['Stress_targets'],sum(r['stress'] for r in rs))
            self.assertTrue(all(g==groups[0] for g in groups))

    def test_pressure_audit_uses_active_request_not_saved_run(self):
        base=json.loads((ROOT/'svb_reference_fit.json').read_text())['request']
        req=AgentExperimentRequest(**{**base,'redemption_pressure_pct':29.1})
        rows=pressure_audit(req)
        self.assertEqual([r['Pressure (%)'] for r in rows],[29.,29.05,29.1,29.15,29.2])
        for row in rows:
            r=req.model_copy(update={'redemption_pressure_pct':row['Pressure (%)']})
            self.assertEqual(row['Request SHA-256'],request_fingerprint(r))
            self.assertAlmostEqual(row['Maximum move (pp)'],simulate_agents(r)['summary']['max_move_from_initial_pct'])

if __name__=='__main__':unittest.main()
