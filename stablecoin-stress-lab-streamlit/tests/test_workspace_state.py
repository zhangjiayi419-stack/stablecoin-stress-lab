"""Regression coverage for page navigation and saved mechanism experiments."""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

class WorkspaceStateChecks(unittest.TestCase):
    def test_submitted_connected_inputs_and_result_survive_navigation(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=30).run()
        app.radio(key='workspace').set_value('Mechanism Lab').run()
        self.assertFalse(app.exception)
        self.assertNotEqual(next(m.value for m in app.metric if m.label=='Debt actually repaid'),'$0')
        app.number_input(key='connected_sell_tokens').set_value(9e6)
        next(b for b in app.button if b.label=='Run connected stress test').click()
        app.run()
        saved=app.session_state['connected_result']
        app.radio(key='workspace').set_value('Overview').run()
        app.radio(key='workspace').set_value('Mechanism Lab').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.number_input(key='connected_sell_tokens').value,9e6)
        self.assertEqual(app.session_state['connected_result'],saved)
        app.radio(key='workspace').set_value('Forecast Lab').run()
        app.select_slider(key='model_horizon').set_value(7).run()
        app.radio(key='workspace').set_value('Overview').run()
        app.radio(key='workspace').set_value('Forecast Lab').run()
        self.assertEqual(app.select_slider(key='model_horizon').value,7)
        self.assertFalse(app.exception)

if __name__=='__main__':unittest.main()
