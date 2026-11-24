import unittest
import numpy as np
import pandas as pd
from bounties.bounty_02_robust_vwap import RobustVWAPEngine

class TestRobustVWAPEngine(unittest.TestCase):
    def test_vwap_clean_series(self):
        engine = RobustVWAPEngine()
        df = pd.DataFrame({
            "price": [100.0, 100.0, 100.0],
            "volume": [10.0, 20.0, 30.0]
        })
        res = engine.calculate_vwap_metrics(df)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["vwap"], 100.0)
        self.assertEqual(res["vwap_variance"], 0.0)
        self.assertEqual(res["outliers_suppressed"], 0)

    def test_vwap_outlier_filtering(self):
        engine = RobustVWAPEngine(mad_threshold=3.5)
        # 9 normal ticks around 100, 1 massive bad oracle spike at 999
        prices = [100.0, 100.2, 99.8, 100.1, 99.9, 100.0, 100.3, 99.7, 100.1, 999.0]
        volumes = [10.0] * 10
        df = pd.DataFrame({"price": prices, "volume": volumes})
        res = engine.calculate_vwap_metrics(df)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["outliers_suppressed"], 1)
        self.assertEqual(res["clean_ticks"], 9)
        self.assertLess(res["vwap"], 101.0)  # Spike eliminated

    def test_vwap_flat_distribution(self):
        engine = RobustVWAPEngine()
        df = pd.DataFrame({
            "price": [50.0, 50.0, 50.0, 50.0, 50.0, 50.0],
            "volume": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        })
        res = engine.calculate_vwap_metrics(df)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["vwap"], 50.0)

    def test_missing_columns(self):
        engine = RobustVWAPEngine()
        df = pd.DataFrame({"p": [1, 2], "v": [3, 4]})
        with self.assertRaises(ValueError):
            engine.calculate_vwap_metrics(df)

if __name__ == "__main__":
    unittest.main()
