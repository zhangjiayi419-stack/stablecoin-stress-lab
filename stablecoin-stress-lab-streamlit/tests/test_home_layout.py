"""Landing-page evidence, session playback, and the explicit case-study route."""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from home_ui import findings
ROOT=Path(__file__).resolve().parents[1]

class LandingChecks(unittest.TestCase):
    def test_findings_are_derived_from_actual_evaluation(self):
        f=findings()
        self.assertAlmostEqual(f['low'],.876675)
        self.assertAlmostEqual(f['improvement'],23.0389443956)
        self.assertEqual(f['targets'],55)
        self.assertLess(f['solver_error'],.000001)
        self.assertLess(f['covariate_improvement'],0)

    def test_home_is_compact_and_intro_does_not_replay(self):
        app=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state['_home_intro_seen'])
        self.assertEqual(app.slider(key='hero_order').value,40.)
        headings=[x.value for x in app.subheader]
        self.assertIn('Key Findings',headings)
        self.assertNotIn('Market context',headings)
        self.assertNotIn('Daily Brief',headings)
        self.assertTrue(any('Optional opening' in str(e.proto) for e in app.get('iframe')))
        app.slider(key='hero_order').set_value(41.).run()
        self.assertFalse(any('Optional opening' in str(e.proto) for e in app.get('iframe')))
        app.radio(key='workspace').set_value('Daily Brief').run()
        self.assertIn('Market context',[x.value for x in app.subheader])
        self.assertIn('The last 30 observed days',[x.value for x in app.subheader])
        app.radio(key='workspace').set_value('Overview').run()
        self.assertFalse(any('Optional opening' in str(e.proto) for e in app.get('iframe')))

    def test_start_here_forces_the_usdc_case(self):
        app=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=30).run()
        app.radio(key='workspace').set_value('Historical Research').run()
        app.selectbox(key='research_case').set_value('USDT · May 2022').run()
        app.radio(key='workspace').set_value('Overview').run()
        next(b for b in app.button if b.label=='Start here: the USDC March 2023 case →').click()
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.radio(key='workspace').value,'Historical Research')
        self.assertEqual(app.selectbox(key='research_case').value,'USDC · March 2023')

if __name__=='__main__':unittest.main()
