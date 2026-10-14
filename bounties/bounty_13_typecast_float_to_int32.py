"""
Production Reference Solution for Tenstorrent tt-metal Issue #55933:
[Bounty] ttnn.typecast(float -> int32) saturates positive overflow to INT32_MIN, inverting the sign on 19.34% of float32 domain.

Target: tenstorrent/tt-metal #55933

Problem:
When typecasting float32 to int32, inputs at or above 2^31 (2,147,483,648.0) saturate to
-2,147,483,648 (INT32_MIN) instead of +2,147,483,647 (INT32_MAX).
This inverts the positive sign to negative across 19.34% of all representable float32 numbers.
Furthermore, NaN converts to -2,147,483,648 rather than 0 (the standard PyTorch convention).

Solution:
IEEE Saturation & NaN Guard:
1. NaN -> 0
2. Inputs >= 2147483647.0 (including +inf) -> +2147483647 (INT32_MAX)
3. Inputs <= -2147483648.0 (including -inf) -> -2147483648 (INT32_MIN)
4. In-range finite values -> standard integer truncation
"""

import math
from typing import Union
import numpy as np

INT32_MAX = 2147483647
INT32_MIN = -2147483648


def cast_float_to_int32_scalar(val: float) -> int:
    """Scalar float32 to int32 with strict IEEE saturation and NaN guard."""
    if math.isnan(val):
        return 0
    if val >= 2147483647.0:
        return INT32_MAX
    if val <= -2147483648.0:
        return INT32_MIN
    return int(val)


def cast_float_to_int32(arr: np.ndarray) -> np.ndarray:
    """
    Vectorized float to int32 conversion with strict IEEE saturation.
    Eliminates positive overflow sign inversion and maps NaN to 0.
    """
    x = np.asarray(arr, dtype=np.float64)

    is_nan = np.isnan(x)
    is_pos_overflow = x >= 2147483647.0
    is_neg_overflow = x <= -2147483648.0

    # In-range conversion
    in_range = ~is_nan & ~is_pos_overflow & ~is_neg_overflow
    result = np.zeros(x.shape, dtype=np.int32)

    result[in_range] = x[in_range].astype(np.int32)
    result[is_pos_overflow] = INT32_MAX
    result[is_neg_overflow] = INT32_MIN
    result[is_nan] = 0

    return result
