"""Economic accounting and boundary behavior; not empirical calibration."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mechanism_engine import Pool, simulate, default_config, default_positions, collateral_at_risk
from backend.app.domain.stable_swap import get_D

class MechanismChecks(unittest.TestCase):
    def test_default_demonstrates_profitable_liquidation_and_recovery(self):
        result=simulate(default_config(),default_positions())
        self.assertGreater(result['summary']['total_debt_repaid_usd'],0)
        self.assertGreater(max(r['at_risk_usd'] for r in result['steps']),0)
        self.assertLess(min(r['price'] for r in result['steps']),.97)
        self.assertIsNotNone(result['summary']['recovery_block'])

    def test_v2_fee_adjusted_constant_product(self):
        p=Pool('Uniswap v2',20e6)
        initial=p.x*p.y
        output,filled=p.trade(1e6)
        self.assertAlmostEqual((10e6+filled*(1-p.fee))*(10e6-output)/initial,1.,places=12)

    def test_curve_fee_adjusted_invariant(self):
        p=Pool('Curve',20e6)
        d=get_D([p.x,p.y],100)
        output,filled=p.trade(1e6)
        self.assertAlmostEqual(get_D([10e6+filled*(1-p.fee),10e6-output],100)/d,1.,places=10)

    def test_v3_crosses_ticks_and_stops_at_edge(self):
        p=Pool('Uniswap v3',20e6)
        x,y=p.balances();out,filled=p.trade(1e12)
        self.assertLess(filled,1e12)
        self.assertAlmostEqual(p.price(),1.0001**-2000,places=10)
        nx,ny=p.balances()
        self.assertAlmostEqual(nx-x,filled*(1-p.fee),places=5)
        self.assertAlmostEqual(y-ny,out,places=5)
        out2,fill2=p.trade(1e6)
        self.assertEqual((out2,fill2),(0.,0.))
        buyout,buyfill=p.trade(1e6,buy=True)
        self.assertGreater(buyout,0);self.assertGreater(buyfill,0)

    def test_lp_withdrawal_keeps_price_reduces_output(self):
        for kind in ('Curve','Uniswap v2','Uniswap v3'):
            p=Pool(kind);q=p.quote(1e6)[0];before=p.price()
            p.withdraw(.6)
            self.assertAlmostEqual(p.price(),before,places=6)
            self.assertLess(p.quote(1e6)[0],q)

    def test_health_factor_boundary(self):
        positions=[dict(collateral_tokens=100.,debt_usd=80.,threshold=.8)]
        self.assertEqual(collateral_at_risk(positions,1.),0)
        self.assertAlmostEqual(collateral_at_risk(positions,.98),98.)

    def test_zero_capital_disables_agents_and_conserves_book(self):
        c=default_config();c.update(arb_capital=0.,liquidator_capital=0.)
        book=default_positions();r=simulate(c,book)
        self.assertEqual(r['ending_positions'],book)
        self.assertEqual(r['summary']['total_debt_repaid_usd'],0)
        self.assertTrue(all(s['arb_spend_usd']==0 for s in r['steps']))

    def test_capital_book_and_lp_bounds(self):
        for kind in ('Curve','Uniswap v2','Uniswap v3'):
            c=default_config();c['kind']=kind
            r=simulate(c,default_positions())
            self.assertTrue(all(s['arb_cash_usd']>=-1e-8 for s in r['steps']))
            self.assertLessEqual(max(s['lp_removed_pct'] for s in r['steps']),c['lp_max']*100+1e-8)
            original=sum(p['debt_usd'] for p in r['initial_positions'])
            ending=sum(p['debt_usd'] for p in r['ending_positions'])
            self.assertAlmostEqual(original-ending,r['summary']['total_debt_repaid_usd'],places=6)
            self.assertTrue(all(p['collateral_tokens']>=0 and p['debt_usd']>=0 for p in r['ending_positions']))

    def test_legacy_lp_withdrawal_independent_of_treasury_mode(self):
        from backend.app.domain.schemas import AgentExperimentRequest
        from backend.app.services.agents import simulate_agents
        request=AgentExperimentRequest(date='2023-03-11',duration_hours=12,redemption_pressure_pct=50,
            pool_liquidity_multiplier=.1,arbitrage_capital_usd=0,lp_max_withdrawal_pct=60,
            lp_risk_threshold_bps=0,treasury_protocol_mode=False)
        result=simulate_agents(request)
        self.assertGreater(result['summary']['lp_cumulative_withdrawal_pct'],0)

    def test_reproducible_and_high_gas_blocks_arbitrage(self):
        c=default_config();self.assertEqual(simulate(c,default_positions()),simulate(c,default_positions()))
        c.update(gas=1e12)
        r=simulate(c,default_positions())
        self.assertTrue(all(s['arb_spend_usd']==0 for s in r['steps']))

if __name__=='__main__':unittest.main()
