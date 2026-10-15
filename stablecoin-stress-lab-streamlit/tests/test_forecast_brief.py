import unittest
import sys
import json
from pathlib import Path
from datetime import date,timedelta
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import forecast_brief as f

class ForecastTests(unittest.TestCase):
    def rows(self):
        start=date(2024,1,1)
        return [dict(asset=a,date_utc=str(start+timedelta(days=i)),close_usd=1+(i%5)*.0001,source='test') for a in ('USDC','USDT') for i in range(70)]
    def test_dates_and_intervals(self):
        result=f.forecast(self.rows(),'USDC')
        self.assertEqual(result['forecast'][0]['date_utc'],'2024-03-11')
        self.assertEqual(result['validation']['n'],40)
        for point in result['forecast']:
            self.assertLessEqual(point['lower_90'],point['upper_90'])
    def test_missing_day_rejected(self):
        with self.assertRaises(ValueError): f.forecast(self.rows()[1:30]+self.rows()[31:],'USDC')
    def test_no_future_leak_in_fit(self):
        rows=self.rows()
        original=f.forecast(rows,'USDC')['validation']['mae_usd']
        # A last-day shock changes only the last held-out error (never earlier fits).
        rows[69]['close_usd']=1.1
        changed=f.forecast(rows,'USDC')['validation']['mae_usd']
        self.assertGreater(changed,original)
    def test_old_data_labeled(self):
        self.assertEqual(f.context(self.rows())['status'],'historical')
    def test_http_contract(self):
        with patch.object(f,'request_json',return_value={'choices':[{'message':{'content':'English brief'},'finish_reason':'stop'}]}) as mock:
            self.assertEqual(f.generate_brief(f.context(self.rows()),key='test-secret'),'English brief')
            url,payload,headers=mock.call_args.args
            self.assertTrue(url.endswith('/v1/chat/completions'))
            self.assertEqual(headers['Authorization'],'Bearer test-secret')
            self.assertIn('HISTORICAL DATA BRIEF',payload['messages'][0]['content'])
    def test_no_key_no_request(self):
        with patch.dict(f.os.environ,{},clear=True), patch.object(f,'request_json') as mock:
            with self.assertRaises(ValueError): f.generate_brief({})
            mock.assert_not_called()
    def test_stale_daily_job_stops(self):
        with patch.object(f,'fetch_current',return_value=self.rows()),patch.object(f,'generate_brief') as mock:
            with self.assertRaises(ValueError): f.run_daily()
            mock.assert_not_called()

if __name__=='__main__': unittest.main()
