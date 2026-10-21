import unittest,json
from pathlib import Path
from streamlit.testing.v1 import AppTest
from snapshot_archive import load_archive,event_rows,EVENTS,execution
ROOT=Path(__file__).resolve().parents[1]

class SnapshotArchiveTests(unittest.TestCase):
    def test_counts_identity_and_provenance(self):
        rows,m=load_archive()
        self.assertEqual(len(rows),843)
        self.assertEqual(m['new_blocks_vs_prior_73_and_346'],662)
        for label,event in EVENTS.items():
            rs=event_rows(rows,event)
            self.assertEqual(len(rs),m['per_event'][event]['unique_blocks'])
            self.assertTrue(all(r['timestamp']<=r['requested_cutoff_utc']<r['next_block_timestamp'] for r in rs))
            self.assertTrue(all(r['chain_id']==1 and r['raw_response_files'] for r in rs))

    def test_selected_block_quotes_match_archived_contract(self):
        rows,m=load_archive()
        for event in EVENTS.values():
            rs=event_rows(rows,event)
            for r in [rs[0],rs[len(rs)//2],rs[-1]]:
                calculated=execution(r,1e6)['net_output']
                self.assertLess(abs(calculated/r['contract_quote_1m_usdc_to_usdt']-1)*10000,1e-6)
                other=execution(r,2e6)['net_output']
                self.assertGreater(other,calculated)
                self.assertLess(other,2*calculated)

    def test_archive_page_can_switch_event_date_block_and_amount(self):
        app=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=30).run()
        app.radio(key='workspace').set_value('Historical Research').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key='archive_event').value,'SVB · March 2023')
        first=app.selectbox(key='archive_block_SVB_2023_03_2023-03-11').value['block_number']
        app.selectbox(key='archive_event').set_value('Terra · May 2022').run()
        self.assertEqual(app.selectbox(key='archive_date_Terra_2022_05').value,'2022-05-12')
        self.assertNotEqual(first,app.selectbox(key='archive_block_Terra_2022_05_2022-05-12').value['block_number'])
        app.number_input(key='archive_sell_amount').set_value(2000000.).run()
        self.assertFalse(app.exception)
        app.selectbox(key='archive_event').set_value('SVB · March 2023').run()
        self.assertEqual(first,app.selectbox(key='archive_block_SVB_2023_03_2023-03-11').value['block_number'])
        self.assertFalse(app.exception)

if __name__=='__main__':unittest.main()
