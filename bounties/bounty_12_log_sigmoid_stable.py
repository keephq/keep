"""
Production Reference Solution for Tenstorrent tt-metal Issue #55457:
[Bounty] ttnn.log_sigmoid diverges to -inf for large positive bfloat16 inputs (x > ~172).

Target: tenstorrent/tt-metal #55457

Problem:
`ttnn.log_sigmoid(x)` is mathematically defined as log(1 / (1 + exp(-x))) = -log(1 + exp(-x)).
The correct asymptotic behavior is log_sigmoid(x) -> 0.0 as x -> +inf.
However, in `ckernel_sfpu_logsigmoid.h`, large positive bfloat16 inputs (x > 172) trigger
arithmetic register overflow in the large-positive branch, growing without bound and returning
-5.71153e+34 at x=256 and -inf at x=266 instead of ~0.0.

Solution:
Numerically Stable Piecewise Formulation:
1. For x >= 20.0: log_sigmoid(x) = 0.0 (in bfloat16 and float32, exp(-20) < 2e-9, which is
   below machine epsilon, so log(1 + exp(-x)) is identically 0.0).
2. For 0 <= x < 20.0: log_sigmoid(x) = -log1p(exp(-x)). Since -x <= 0, exp(-x) in (0, 1],
   overflow is mathematically impossible.
3. For x < 0.0: log_sigmoid(x) = x - log1p(exp(x)). Since x < 0, exp(x) in (0, 1],
   overflow is mathematically impossible.
"""

import math
from typing import Union
import numpy as np


def stable_log_sigmoid_scalar(x: float) -> float:
    """Computes overflow-safe log_sigmoid for scalar input."""
    if math.isnan(x):
        return float('nan')
    if x == float('-inf'):
        return float('-inf')
    if x == float('inf') or x >= 20.0:
        return 0.0

    if x >= 0.0:
        # -log(1 + exp(-x))
        return -math.log1p(math.exp(-x))
    else:
        # x - log(1 + exp(x))
        return x - math.log1p(math.exp(x))


def stable_log_sigmoid(x: np.ndarray, dtype=np.float32) -> np.ndarray:
    """
    Vectorized overflow-safe log_sigmoid supporting float32 and bfloat16 ranges.
    Guarantees x > 172 asymptotically saturates to 0.0 rather than -inf.
    """
    arr = np.asarray(x, dtype=np.float64)

    # Condition 1: x >= 20.0 -> exact 0.0
    # Condition 2: 0 <= x < 20.0 -> -log1p(exp(-x))
    # Condition 3: x < 0.0 -> x - log1p(exp(x))
    pos_mask = (arr >= 0.0) & (arr < 20.0)
    neg_mask = arr < 0.0
    inf_pos_mask = arr >= 20.0

    result = np.zeros_like(arr)

    # Compute pos branch safely (clip to avoid underflow/overflow warnings)
    safe_pos_arr = np.clip(arr, 0.0, 88.0)
    pos_vals = -np.log1p(np.exp(-safe_pos_arr))
    result = np.where(pos_mask, pos_vals, result)

    # Compute neg branch safely
    safe_neg_arr = np.clip(arr, -88.0, 0.0)
    neg_vals = arr - np.log1p(np.exp(safe_neg_arr))
    result = np.where(neg_mask, neg_vals, result)
    # Clamp large positive to 0.0
    result = np.where(inf_pos_mask, 0.0, result)

    # Handle -inf -> -inf
    result = np.where(np.isneginf(arr), -np.inf, result)

    return result.astype(dtype)
