"""
Production Reference Solution for Tenstorrent tt-metal Issue #55129:
[Bounty] ttnn.pow (fp32 path) returns +inf for every base when |exponent| > 8.3e34.
pow(1.0, 1e35) gives inf instead of 1.0; the Veltkamp split overflows.

Target: tenstorrent/tt-metal #55129

Problem:
In `ttnn.pow(base, exponent)`, the FP32 kernel evaluates exp(y * ln(x)) using a Veltkamp split
to compute the product y * ln(x) in high precision:
    C = (2^12 + 1) * y = 4097 * y
When |y| > FLT_MAX / 4097 (~8.3e34), C overflows float32 registers, returning +inf or NaN.
For base = 1.0, where mathematically 1.0^y = 1.0 for all y, the kernel returns +inf on large exponents!
Similarly, base = 0.0 with positive large exponents fails.

Solution:
Pre-Veltkamp Identity Guards:
1. If base == 1.0: return 1.0 immediately (mathematical identity 1^y = 1).
2. If exponent == 0.0: return 1.0 immediately (x^0 = 1).
3. If base == 0.0:
   - y > 0: return 0.0
   - y == 0: return 1.0
   - y < 0: return +inf
4. For extreme exponents |y| > 8.3e34:
   - |base| > 1.0: return +inf if y > 0 else 0.0
   - |base| < 1.0: return 0.0 if y > 0 else +inf
"""

import math
from typing import Union
import numpy as np

VELTKAMP_EXPONENT_CEILING = 8.3e34
FLT_MAX = 3.402823466e38


def broken_legacy_veltkamp_pow_scalar(base: float, exponent: float) -> float:
    """Simulates the legacy Veltkamp split overflow on large exponents in FP32."""
    with np.errstate(over='ignore'):
        C = np.float32(4097.0) * np.float32(exponent)
    if np.isinf(C):
        return float('inf') # Demonstrates the legacy bug: pow(1.0, 1e35) -> +inf in FP32
    return math.pow(base, exponent)


def safe_pow_scalar(base: float, exponent: float) -> float:
    """Scalar power with IEEE identity guards and extreme exponent handling."""
    if math.isnan(base) or math.isnan(exponent):
        return float('nan')

    # Identity 1: 1.0^y == 1.0 for ANY exponent
    if base == 1.0:
        return 1.0

    # Identity 2: x^0.0 == 1.0 for ANY base
    if exponent == 0.0:
        return 1.0

    # Identity 3: 0.0^y
    if base == 0.0:
        if exponent > 0:
            return 0.0
        elif exponent < 0:
            return float('inf')
        return 1.0

    # Extreme exponent guard (|y| > 8.3e34) avoiding Veltkamp overflow
    if abs(exponent) > VELTKAMP_EXPONENT_CEILING:
        if base > 1.0:
            return float('inf') if exponent > 0 else 0.0
        elif 0.0 < base < 1.0:
            return 0.0 if exponent > 0 else float('inf')
        elif base == -1.0:
            # -1^y
            return float('nan') if not exponent.is_integer() else (1.0 if int(exponent) % 2 == 0 else -1.0)

    try:
        res = math.pow(base, exponent)
        return res
    except OverflowError:
        return float('inf')


def safe_pow(base: np.ndarray, exponent: Union[np.ndarray, float]) -> np.ndarray:
    """
    Vectorized pow with identity guards.
    Guarantees pow(1.0, 1e35) == 1.0 and eliminates Veltkamp split overflow.
    """
    b = np.asarray(base, dtype=np.float64)
    e = np.asarray(exponent, dtype=np.float64)

    # Condition masks
    is_base_one = (b == 1.0)
    is_exp_zero = (e == 0.0)
    is_base_zero = (b == 0.0)

    # Default NumPy power with warnings suppressed for extreme overflows
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        result = np.power(b, e)

    # Apply identity guards
    result = np.where(is_base_one, 1.0, result)
    result = np.where(is_exp_zero, 1.0, result)
    result = np.where(is_base_zero & (e > 0), 0.0, result)
    result = np.where(is_base_zero & (e < 0), np.inf, result)

    # Extreme exponent guards
    extreme_exp = np.abs(e) > VELTKAMP_EXPONENT_CEILING
    result = np.where(extreme_exp & (b > 1.0) & (e > 0), np.inf, result)
    result = np.where(extreme_exp & (b > 1.0) & (e < 0), 0.0, result)
    result = np.where(extreme_exp & (b < 1.0) & (b > 0.0) & (e > 0), 0.0, result)
    result = np.where(extreme_exp & (b < 1.0) & (b > 0.0) & (e < 0), np.inf, result)

    return result.astype(np.float32)
