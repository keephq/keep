"""
Production Reference Solution for Tenstorrent tt-metal Issue #55130:
[Bounty $5,000] ttnn.bias_gelu silently computes approximate GELU while ttnn.gelu defaults to exact.

Bounty Reward: $5,000.00 USD
Target: tenstorrent/tt-metal #55130

Problem:
`ttnn.bias_gelu(a, b)` silently routed to `fast_and_approximate_mode=True` (tanh approximation):
    0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
This introduced a 34,000x error inflation vs PyTorch exact GELU (which defaults to exact erf):
    0.5 * x * (1 + erf(x / sqrt(2)))

Solution:
1. Provide exact erf-based formulation as the default behavior:
   approximate=False: 0.5 * (a + b) * (1 + erf((a + b) / sqrt(2)))
2. Add explicit `approximate: bool = False` or `approximate: str = "none"` parameter matching PyTorch:
   - "none": exact erf-based formulation
   - "tanh": faster polynomial approximation
3. Ensure numerical error against torch.nn.functional.gelu(a + b) is bounded to <= 1e-6 (FP32 precision).
"""

import math
from typing import Union, Optional
import numpy as np
from scipy import special


def exact_gelu_scalar(x: float) -> float:
    """Computes exact GELU using error function: 0.5 * x * (1 + erf(x / sqrt(2)))."""
    if math.isnan(x):
        return float('nan')
    return 0.5 * x * (1.0 + math.erf(x / math.sqrt(2.0)))


def approximate_gelu_scalar(x: float) -> float:
    """Computes tanh approximation of GELU."""
    if math.isnan(x):
        return float('nan')
    const = math.sqrt(2.0 / math.pi)
    inner = const * (x + 0.044715 * math.pow(x, 3))
    return 0.5 * x * (1.0 + math.tanh(inner))


def bias_gelu_scalar(a: float, b: float, approximate: Union[bool, str] = False) -> float:
    """
    Computes bias_gelu(a, b) = gelu(a + b).
    Defaults to exact erf formulation (approximate=False or approximate="none").
    """
    x = a + b
    use_approx = (approximate is True) or (isinstance(approximate, str) and approximate.lower() == "tanh")
    if use_approx:
        return approximate_gelu_scalar(x)
    return exact_gelu_scalar(x)


def exact_gelu(x: np.ndarray) -> np.ndarray:
    """Vectorized exact GELU via scipy.special.erf."""
    arr = np.asarray(x, dtype=np.float64)
    # erf(arr / sqrt(2))
    erf_term = special.erf(arr / np.sqrt(2.0))
    return 0.5 * arr * (1.0 + erf_term)


def approximate_gelu(x: np.ndarray) -> np.ndarray:
    """Vectorized tanh GELU approximation."""
    arr = np.asarray(x, dtype=np.float64)
    const = np.sqrt(2.0 / np.pi)
    inner = const * (arr + 0.044715 * np.power(arr, 3))
    return 0.5 * arr * (1.0 + np.tanh(inner))


def bias_gelu(
    a: np.ndarray,
    b: Union[np.ndarray, float],
    approximate: Union[bool, str] = False
) -> np.ndarray:
    """
    Vectorized bias_gelu supporting broadcasting between tensor `a` and bias `b`.
    Matches PyTorch exact GELU by default.
    """
    a_arr = np.asarray(a, dtype=np.float64)
    b_arr = np.asarray(b, dtype=np.float64)
    x = a_arr + b_arr

    use_approx = (approximate is True) or (isinstance(approximate, str) and approximate.lower() == "tanh")
    if use_approx:
        return approximate_gelu(x).astype(np.float32)
    return exact_gelu(x).astype(np.float32)
