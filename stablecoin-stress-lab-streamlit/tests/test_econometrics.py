import sys,unittest,math
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from econometrics import evaluate_intervals,setar_fit,winkler
from mechanism_engine import Pool

def series():return [((date(2023,1,1)+timedelta(days=i)).isoformat(),1+.0001*math.sin(i/3)) for i in range(85)]

class EconometricChecks(unittest.TestCase):
    def test_winkler_penalizes_misses(self):
        self.assertAlmostEqual(winkler(1.,.9,1.1),.2)
        self.assertAlmostEqual(winkler(.8,.9,1.1),2.2)
    def test_interval_inputs_are_chronological(self):
        a=series();b=a[:70]+[(d,.85) for d,_ in a[70:]]
        aa=evaluate_intervals(a,3,models=['Persistence','SETAR'])
        bb=evaluate_intervals(b,3,models=['Persistence','SETAR'])
        fields=['origin','prediction_usd','lower_usd','upper_usd','calibration_count','alpha_used']
        before=lambda r:[[x[k] for k in fields] for x in r['predictions'] if x['origin']<a[70][0]]
        self.assertEqual(before(aa),before(bb))
    def test_same_origins_and_nonnegative_width(self):
        r=evaluate_intervals(series(),7,models=['Persistence','SETAR'])
        sets=[{x['origin'] for x in r['predictions'] if x['model']==m} for m in ['Persistence','SETAR']]
        self.assertEqual(*sets)
        self.assertTrue(all(x['lower_usd']<=x['upper_usd'] and x['calibration_count']>=20 for x in r['predictions']))
        self.assertEqual(sets[0].pop()[:4],'2023')
    def test_constant_prices_have_finite_intervals(self):
        r=evaluate_intervals([(d,1.) for d,_ in series()],1,models=['Persistence','SETAR'])
        self.assertTrue(all(x['MAE_bps']==0 and x['Coverage_pct']==100 and x['Mean_width_bps']==0 for x in r['scores']))
    def test_narrow_v3_exhaustion_preserves_unfilled_input(self):
        p=Pool('Uniswap v3',outer_share=0.)
        capacity=p.sell_capacity_to_price(1.0001**-200)
        out,filled=p.trade(capacity*2)
        self.assertAlmostEqual(filled/capacity,1.,places=9)
        self.assertAlmostEqual(p.price(),1.0001**-200,places=10)
        self.assertEqual(p.active_liquidity(),0.)
        self.assertEqual(p.trade(1000.),(0.,0.))
    def test_layered_pool_retains_outer_liquidity(self):
        p=Pool('Uniswap v3');l=p.active_liquidity()
        p.trade(p.sell_capacity_to_price(1.0001**-200)+100)
        self.assertGreater(p.active_liquidity(),0.)
        self.assertLess(p.active_liquidity(),l)

if __name__=='__main__':unittest.main()
