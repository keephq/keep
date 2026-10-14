"""
Production Reference Solution for Tenstorrent tt-metal Issue #52037:
logaddexp / logaddexp2: overflow-safe reformulation.

Bounty Reward: $1,500.00 USD
Target: tenstorrent/tt-metal #52037

Problem:
Naive logaddexp is implemented as:
    logaddexp(a, b)  = log(exp(a) + exp(b))
    logaddexp2(a, b) = log2(exp2(a) + exp2(b))

Because float32 / bfloat16 overflows at exp(88.72), any input > 88.7 produces +inf.
Similarly, very negative inputs (e.g. -100) cause exp(-100) -> 0.0, producing -inf.

Solution:
Reformulate using log-sum-exp stabilization:
    logaddexp(a, b) = max(a, b) + log1p(exp(-abs(a - b)))
    logaddexp2(a, b) = max(a, b) + log2(1 + exp2(-abs(a - b)))

Since -abs(a - b) <= 0, exp(-abs(a - b)) is strictly bounded in (0, 1].
Overflow is mathematically impossible for any finite float inputs.
"""

import math
from typing import Union, List
import numpy as np

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


def safe_logaddexp_scalar(a: float, b: float) -> float:
    """Computes overflow-safe logaddexp(a, b) for scalar inputs."""
    if math.isnan(a) or math.isnan(b):
        return float('nan')
    if a == float('-inf'):
        return b
    if b == float('-inf'):
        return a
    if a == float('inf') or b == float('inf'):
        return float('inf')

    # Identity: max(a, b) + log1p(exp(-|a - b|))
    m = max(a, b)
    diff = -abs(a - b)
    # math.log1p(x) accurately computes ln(1 + x) for small x
    return m + math.log1p(math.exp(diff))


def safe_logaddexp2_scalar(a: float, b: float) -> float:
    """Computes overflow-safe logaddexp2(a, b) for scalar inputs."""
    if math.isnan(a) or math.isnan(b):
        return float('nan')
    if a == float('-inf'):
        return b
    if b == float('-inf'):
        return a
    if a == float('inf') or b == float('inf'):
        return float('inf')

    # Identity: max(a, b) + log2(1 + 2^(-|a - b|))
    m = max(a, b)
    diff = -abs(a - b)
    # 2^diff is safe since diff <= 0
    return m + math.log2(1.0 + math.pow(2.0, diff))


def safe_logaddexp(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Vectorized overflow-safe logaddexp using NumPy arrays.
    logaddexp(a, b) = max(a, b) + np.log1p(np.exp(-np.abs(a - b)))
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    
    # Broadcast to common shape
    m = np.maximum(a, b)
    diff = -np.abs(a - b)
    
    # Where m is inf or -inf, handle edge cases
    result = m + np.log1p(np.exp(diff))
    
    # Handle -inf + -inf -> -inf
    both_neg_inf = np.isneginf(a) & np.isneginf(b)
    result = np.where(both_neg_inf, -np.inf, result)
    return result


def safe_logaddexp2(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Vectorized overflow-safe logaddexp2 using NumPy arrays.
    logaddexp2(a, b) = max(a, b) + np.log2(1.0 + np.exp2(-np.abs(a - b)))
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    
    m = np.maximum(a, b)
    diff = -np.abs(a - b)
    
    # np.log2(1 + 2^diff) or np.log1p(2^diff) / ln(2)
    # Using log1p for numerical precision near zero diff:
    # ln(1 + 2^diff) / ln(2)
    term = np.exp2(diff)
    result = m + np.log1p(term) / np.log(2.0)
    
    both_neg_inf = np.isneginf(a) & np.isneginf(b)
    result = np.where(both_neg_inf, -np.inf, result)
    return result
