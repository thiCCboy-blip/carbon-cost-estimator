"""Smoke tests for the carbon-cost engine (stdlib unittest, no pytest needed)."""

import unittest

from carbon_model import CarbonCostModel


class TestCarbonCostModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = CarbonCostModel()
        cls.base = cls.model.baseline()

    def test_baseline_positive(self):
        self.assertGreater(self.base.baseline_cost, 0)
        self.assertGreater(self.base.baseline_carbon, 0)

    def test_all_swaps_reduce_carbon(self):
        full = self.model.swap_all_alternatives()
        self.assertLess(full.scenario_carbon, full.baseline_carbon)

    def test_single_swap_math(self):
        alts = self.model.alternatives_map()
        mid = next(iter(alts))
        res = self.model.scenario([mid])
        s = res.swaps[0]
        # carbon delta must equal (alt_cf - base_cf) * qty / 1000
        m = self.model.material(mid)
        expected = (float(m["alt_carbon_factor_kgco2e_per_unit"]) - float(m["carbon_factor_kgco2e_per_unit"])) * s.quantity / 1000
        self.assertAlmostEqual(s.delta_carbon, expected, places=6)

    def test_breakeven_when_premium(self):
        # Green concrete has a cost premium -> breakeven price should exist
        res = self.model.scenario(["C01"])
        be = res.breakeven_carbon_price()
        self.assertIsNotNone(be)
        self.assertGreater(be, 0)

    def test_intensity(self):
        i = self.base.carbon_intensity()
        self.assertGreater(i, 0)

    def test_excel_bytes(self):
        blob = self.model.to_excel(self.base, 350.0)
        self.assertTrue(blob[:2] == b"PK")  # xlsx zip magic


class TestBoqUpload(unittest.TestCase):
    def setUp(self):
        self.model = CarbonCostModel()

    def _sample(self):
        import pandas as pd

        return pd.DataFrame(
            [
                {"description": "Test concrete", "material_id": "C01", "quantity": 100, "unit": "m3"},
                {"description": "Test steel", "material_id": "S02", "quantity": 50, "unit": "tonne"},
            ]
        )

    def test_valid_upload_replaces_boq(self):
        msgs = self.model.set_boq(self._sample())
        self.assertEqual(len(self.model.boq), 2)
        self.assertTrue(any("2 BOQ line(s) accepted" in m for m in msgs))
        res = self.model.baseline()
        expected_cost = 100 * 420 + 50 * 4800
        self.assertAlmostEqual(res.baseline_cost, expected_cost)

    def test_unknown_material_dropped(self):
        import pandas as pd

        df = self._sample()
        df.loc[len(df)] = {"description": "Ghost", "material_id": "ZZZ", "quantity": 1, "unit": "ea"}
        msgs = self.model.set_boq(df)
        self.assertEqual(len(self.model.boq), 2)
        self.assertTrue(any("not in the" in m for m in msgs))

    def test_missing_column_raises(self):
        import pandas as pd

        with self.assertRaises(ValueError):
            self.model.set_boq(pd.DataFrame([{"description": "x"}]))

    def test_bad_quantity_dropped(self):
        import pandas as pd

        df = self._sample()
        df.loc[len(df)] = {"description": "Bad", "material_id": "C01", "quantity": -5, "unit": "m3"}
        msgs = self.model.set_boq(df)
        self.assertEqual(len(self.model.boq), 2)
        self.assertTrue(any("quantity" in m for m in msgs))

    def test_reset_restores_default(self):
        self.model.set_boq(self._sample())
        self.model.reset_boq()
        self.assertEqual(len(self.model.boq), len(self.model._default_boq))


if __name__ == "__main__":
    unittest.main()
