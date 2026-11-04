"""
Production Reference Solution for Tenstorrent tt-metal Issue #55585:
[Bounty] moreh_norm_backward returns NaN for all-zero reduced slices, where gradient is finite.

Target: tenstorrent/tt-metal #55585

Mathematical Definition:
    Forward Lp Norm:
        y = norm(x, p) = (sum(|x_i|^p))^(1/p)

    Backward Gradient:
        dx_i = dy * sign(x_i) * |x_i|^(p-1) * y^(1-p)
        For p = 2: dx_i = dy * (x_i / y)

Problem:
When an input slice is all zeros (e.g. x = [0.0, 0.0, 0.0]), the forward norm is y = 0.0.
The legacy backward composite kernel evaluates (x_i / y), leading to 0.0 / 0.0 = NaN.
In standard PyTorch autograd, the gradient for all-zero slices is mathematically defined as 0.0.
Returning NaN corrupts backpropagation across networks containing zero-padded tokens.

Solution:
Zero-Norm Finite Guard:
    grad_input = where(y == 0.0, 0.0, dy * sign(x) * |x|^(p-1) * (y + eps)^(1-p))
    or explicitly clamping / zeroing outputs where the reduced norm is identically zero.
"""

from typing import Union, Tuple, Optional
import numpy as np


def moreh_norm_backward_scalar(
    grad_output: float,
    x: float,
    norm_y: float,
    p: float = 2.0
) -> float:
    """Scalar backward computation with zero-norm guard."""
    if norm_y == 0.0:
        return 0.0

    if p == 2.0:
        return float(grad_output * (x / norm_y))

    # General Lp norm
    sign_x = 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)
    term1 = abs(x) ** (p - 1.0)
    term2 = norm_y ** (1.0 - p)
    return float(grad_output * sign_x * term1 * term2)


def moreh_norm_backward(
    grad_output: np.ndarray,
    x: np.ndarray,
    p: float = 2.0,
    dim: Optional[int] = None,
    keepdim: bool = True
) -> np.ndarray:
    """
    Vectorized moreh_norm_backward with zero-norm finite guard.
    Guarantees all-zero slices return 0.0 instead of NaN.
    """
    x_arr = np.asarray(x, dtype=np.float32)
    dy_arr = np.asarray(grad_output, dtype=np.float32)

    # Compute forward norm
    abs_x = np.abs(x_arr)
    if dim is None:
        if p == 2.0:
            y = np.sqrt(np.sum(np.square(x_arr)))
        else:
            y = np.sum(np.power(abs_x, p)) ** (1.0 / p)
    else:
        if p == 2.0:
            y = np.sqrt(np.sum(np.square(x_arr), axis=dim, keepdims=keepdim))
        else:
            y = np.sum(np.power(abs_x, p), axis=dim, keepdims=keepdim) ** (1.0 / p)

    # Zero-norm mask: where norm is zero or non-finite
    is_zero_norm = (y == 0.0) | np.isnan(y)

    if p == 2.0:
        # Safe division: where norm is zero, divide by 1.0 then zero out
        safe_y = np.where(is_zero_norm, 1.0, y)
        raw_grad = dy_arr * (x_arr / safe_y)
        grad_input = np.where(is_zero_norm, 0.0, raw_grad)
    else:
        safe_y = np.where(is_zero_norm, 1.0, y)
        sign_x = np.sign(x_arr)
        term1 = np.power(abs_x, p - 1.0)
        term2 = np.power(safe_y, 1.0 - p)
        raw_grad = dy_arr * sign_x * term1 * term2
        grad_input = np.where(is_zero_norm, 0.0, raw_grad)

    return grad_input.astype(np.float32)
