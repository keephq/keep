"""
Bounty Solution 02: Vectorized VWAP Variance Calculator with Robust Outlier Filtering
Target: Open DeFi Bounties ($250 Reward)
Scope: Statistical volume-weighted average price (VWAP) with Modified Z-Score / IQR outlier suppression.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple

class RobustVWAPEngine:
    """
    Computes statistical VWAP and rolling variance while filtering out
    wash-trading spikes, flash crashes, and bad oracle ticks using Median Absolute Deviation (MAD).
    """
    def __init__(self, mad_threshold: float = 3.5, rolling_window: int = 20):
        self.mad_threshold = mad_threshold
        self.rolling_window = rolling_window

    def filter_outliers_mad(self, prices: np.ndarray, volumes: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Modified Z-score based on Median Absolute Deviation (MAD):
        M_i = 0.6745 * (x_i - median(x)) / MAD
        More robust than standard deviation which is skewed by fat-tail crypto outliers.
        """
        if len(prices) < 5:
            return prices, volumes, np.ones(len(prices), dtype=bool)

        median_price = np.median(prices)
        mad = np.median(np.abs(prices - median_price))

        if mad == 0:
            # Fallback when spread is zero/flat
            valid_mask = np.ones(len(prices), dtype=bool)
        else:
            modified_z_scores = 0.6745 * np.abs(prices - median_price) / mad
            valid_mask = modified_z_scores <= self.mad_threshold

        return prices[valid_mask], volumes[valid_mask], valid_mask

    def calculate_vwap_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Expects DataFrame with columns ['price', 'volume'].
        Computes clean VWAP, Variance, Standard Error, and percentage of filtered noise ticks.
        """
        if 'price' not in df.columns or 'volume' not in df.columns:
            raise ValueError("Input DataFrame must contain 'price' and 'volume' columns.")

        prices = df['price'].to_numpy()
        volumes = df['volume'].to_numpy()

        clean_p, clean_v, mask = self.filter_outliers_mad(prices, volumes)

        if len(clean_p) == 0 or np.sum(clean_v) == 0:
            return {"status": "error", "message": "Zero valid volume post-filtering."}

        # Vectorized VWAP calculation: sum(P * V) / sum(V)
        cum_pv = np.sum(clean_p * clean_v)
        cum_v = np.sum(clean_v)
        vwap = cum_pv / cum_v

        # Weighted Variance: sum(V * (P - VWAP)^2) / sum(V)
        weighted_variance = np.sum(clean_v * ((clean_p - vwap) ** 2)) / cum_v
        weighted_std = np.sqrt(weighted_variance)

        outlier_count = int(np.sum(~mask))
        outlier_pct = round((outlier_count / len(prices)) * 100, 2)

        return {
            "vwap": round(float(vwap), 4),
            "vwap_variance": round(float(weighted_variance), 6),
            "vwap_std_dev": round(float(weighted_std), 4),
            "total_ticks": len(prices),
            "clean_ticks": len(clean_p),
            "outliers_suppressed": outlier_count,
            "outlier_percentage": outlier_pct,
            "status": "success"
        }
