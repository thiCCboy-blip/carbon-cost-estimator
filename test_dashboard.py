"""End-to-end dashboard test using Streamlit's AppTest harness."""

import unittest

from streamlit.testing.v1 import AppTest


class TestDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.at = AppTest.from_file("app.py", default_timeout=90)
        cls.at.run()

    def test_no_exceptions(self):
        self.assertEqual([str(e.value) for e in self.at.exception], [])

    def test_kpis_rendered(self):
        self.assertGreaterEqual(len(self.at.metric), 4)

    def test_swap_flow(self):
        at = AppTest.from_file("app.py", default_timeout=90)
        at.run()
        # toggle "swap all"
        at.toggle[0].set_value(True)
        at.run()
        self.assertEqual([str(e.value) for e in at.exception], [])
        self.assertGreaterEqual(len(at.metric), 8)

    def test_excel_button_present(self):
        self.assertGreaterEqual(len(self.at.download_button), 1)


if __name__ == "__main__":
    unittest.main()
