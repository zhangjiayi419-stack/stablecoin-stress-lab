"""Numerical consistency checks; not an on-chain accuracy benchmark."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.domain.stable_swap import get_D, quote_swap
from backend.app.services.replay import load_pool_state

class ExecutionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=next(s for s in load_pool_state() if s['timestamp'].startswith('2023-03-11'))
    def test_gross_output_preserves_invariant(self):
        for i,j in [(1,2),(2,1)]:
            balances=[float(self.snapshot[k]) for k in ['dai_pool','usdc_pool','usdt_pool']]
            r=quote_swap(self.snapshot,i,j,1_000_000.)
            updated=balances.copy();updated[i]+=1_000_000.;updated[j]-=r['gross_output']
            d=get_D(balances,float(self.snapshot['amp']))
            self.assertAlmostEqual(get_D(updated,float(self.snapshot['amp']))/d,1.,places=10)
    def test_fee_arithmetic(self):
        r=quote_swap(self.snapshot,1,2,1_000_000.)
        self.assertAlmostEqual(r['net_output']+r['fee_amount'],r['gross_output'],places=6)
        self.assertAlmostEqual(r['net_output']/r['gross_output'],1-float(self.snapshot['fee_rate']),places=12)
    def test_homogeneous_scaling(self):
        a=quote_swap(self.snapshot,1,2,1_000_000.)
        b=quote_swap(self.snapshot,1,2,2_000_000.,2.)
        self.assertAlmostEqual(b['net_output']/a['net_output'],2.,places=9)
    def test_more_depth_reduces_fixed_sale_impact(self):
        a=quote_swap(self.snapshot,1,2,1_000_000.)
        b=quote_swap(self.snapshot,1,2,1_000_000.,1.3)
        self.assertGreater(b['net_output'],a['net_output'])
        self.assertLess(b['price_impact_ex_fee_pct'],a['price_impact_ex_fee_pct'])
    def test_larger_sale_has_worse_average_execution(self):
        a=quote_swap(self.snapshot,1,2,100_000.)
        b=quote_swap(self.snapshot,1,2,10_000_000.)
        self.assertLess(b['average_execution_price_net'],a['average_execution_price_net'])

if __name__=='__main__':unittest.main()
