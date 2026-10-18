"""Regression checks for the reported 15% cross-scenario mismatch."""
import json
import unittest
from pathlib import Path
from backend.app.domain.schemas import AgentExperimentRequest
from backend.app.services.agents import simulate_agents
from participant_comparison import matched_phase_diagram,selected_cell
from forecast_ui import projection_figure
from forecast_brief import forecast

ROOT=Path(__file__).resolve().parents[1]

class ComparisonChecks(unittest.TestCase):
    def test_selected_cell_matches_same_request_and_premium_is_not_discount(self):
        fitted=json.loads((ROOT/'svb_reference_fit.json').read_text())
        req=AgentExperimentRequest(**fitted['request']).model_copy(update={'redemption_pressure_pct':15.})
        path=simulate_agents(req);phase=matched_phase_diagram(req);cell=selected_cell(phase,req)
        for name in ['max_move_from_initial_pct','max_depeg_depth_pct','max_premium_pct']:
            self.assertAlmostEqual(cell[name],path['summary'][name],places=10)
        self.assertAlmostEqual(cell['max_move_from_initial_pct'],.08759010136127898,places=7)
        self.assertEqual(cell['max_depeg_depth_pct'],0)
        self.assertGreater(path['summary']['ending_pool_implied_usdc_usd'],1)
        self.assertEqual(phase['assumptions']['date'],'2023-03-10')
        self.assertEqual(len(phase['cells']),48)
        with self.assertRaises(ValueError):selected_cell(phase,req.model_copy(update={'date':req.date.replace(day=11)}))

    def test_non_grid_depth_is_executed_and_reference_is_consistent(self):
        fitted=json.loads((ROOT/'svb_reference_fit.json').read_text())
        req=AgentExperimentRequest(**fitted['request'])
        self.assertAlmostEqual(selected_cell(matched_phase_diagram(req),req)['max_move_from_initial_pct'],fitted['result']['summary']['max_move_from_initial_pct'],places=10)
        req=req.model_copy(update={'pool_liquidity_multiplier':1.1,'redemption_pressure_pct':15.})
        self.assertEqual(selected_cell(matched_phase_diagram(req),req)['liquidity_multiplier'],1.1)

    def test_validation_chart_has_explicit_date_ticks_for_all_horizons(self):
        rows=json.loads((ROOT/'reports/prices_latest.json').read_text())
        for h in [1,3,7]:
            result=forecast(rows,'USDC',h);fig=projection_figure(result)
            dates=[r['date_utc'] for r in result['forecast']]
            self.assertEqual(fig.layout.xaxis.type,'category')
            self.assertEqual(list(fig.layout.xaxis.ticktext),dates)
            self.assertEqual(list(fig.layout.xaxis.tickvals),dates)
            self.assertEqual(len(fig.layout.xaxis.ticktext),h)
            if h==1:self.assertTrue(fig.data[0].error_y.visible)

if __name__=='__main__':unittest.main()
