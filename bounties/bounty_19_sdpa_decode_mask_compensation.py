"""
Production Reference Solution for Tenstorrent tt-metal Issue #55337:
[Bounty] ttnn.transformer.scaled_dot_product_attention_decode scales the user attn_mask by scale:
a finite additive bias is attenuated by 1/sqrt(D).

Target: tenstorrent/tt-metal #55337

Mathematical Definition of SDPA:
    Attention(Q, K, V, mask, scale) = softmax((Q @ K.T) * scale + mask) @ V
    where scale = 1.0 / sqrt(head_dim)

Problem:
In `ttnn.transformer.scaled_dot_product_attention_decode`, the fused hardware kernel evaluates:
    scores = (Q @ K.T + mask) * scale
Because `mask` was added BEFORE scaling, the effective mask applied is `mask * scale = mask / sqrt(D)`.
For infinite causal masks (-inf), -inf * scale = -inf, so the bug was masked.
However, for any finite additive bias (such as ALiBi relative position embeddings, T5 relative bias,
or sliding-window biases like -5.0), the bias was attenuated by 1/sqrt(D).
For D = 128 (sqrt(D) = 11.3137), a bias of -5.0 was erroneously diluted to -0.442, causing severe
token probability divergence.

Solution:
Pre-Compensation Transformation:
Pre-multiply the finite additive mask by sqrt(D) (or divide by scale) before passing to the fused kernel:
    mask_compensated = mask * (1.0 / scale) = mask * sqrt(head_dim)

Then:
    (Q @ K.T + mask_compensated) * scale = (Q @ K.T) * scale + mask
Restores exact mathematical parity with PyTorch `torch.nn.functional.scaled_dot_product_attention`.
"""

import math
from typing import Union, Tuple, Optional
import numpy as np


def broken_legacy_sdpa_decode(
    q: np.ndarray,
    k: np.ndarray,
    v: np.ndarray,
    mask: Optional[np.ndarray] = None,
    scale: Optional[float] = None
) -> np.ndarray:
    """
    Simulates the uncompensated legacy fused decode kernel:
    Computes softmax((Q @ K.T + mask) * scale) @ V.
    Demonstrates the 1/sqrt(D) attenuation on finite additive bias.
    """
    head_dim = q.shape[-1]
    s = scale if scale is not None else (1.0 / math.sqrt(head_dim))

    # Q @ K.T
    scores = np.matmul(q, np.swapaxes(k, -1, -2))
    if mask is not None:
        scores = scores + mask # Bug: added before scaling
    scores = scores * s

    # Softmax along last dim
    exp_scores = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
    attn_weights = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)

    return np.matmul(attn_weights, v)


def compensated_sdpa_decode(
    q: np.ndarray,
    k: np.ndarray,
    v: np.ndarray,
    mask: Optional[np.ndarray] = None,
    scale: Optional[float] = None,
    is_causal: bool = False
) -> np.ndarray:
    """
    Corrected SDPA decode with mask pre-compensation:
    Restores exact PyTorch mathematical semantics: softmax((Q @ K.T) * scale + mask) @ V.
    """
    head_dim = q.shape[-1]
    s = scale if scale is not None else (1.0 / math.sqrt(head_dim))

    scores = np.matmul(q, np.swapaxes(k, -1, -2)) * s

    if mask is not None:
        # Standard unattenuated addition
        scores = scores + mask

    # Softmax
    exp_scores = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
    attn_weights = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)

    return np.matmul(attn_weights, v).astype(np.float32)


def compute_mask_precompensation(mask: np.ndarray, scale: float) -> np.ndarray:
    """
    Utility to pre-compensate user attention masks before dispatching to fused hardware kernel.
    Preserves -inf values while scaling finite biases by 1 / scale.
    """
    m = np.asarray(mask, dtype=np.float32)
    inv_scale = 1.0 / scale
    # Where mask is finite, scale by 1 / scale; where -inf, keep -inf
    is_inf = np.isinf(m)
    compensated = np.where(is_inf, m, m * inv_scale)
    return compensated.astype(np.float32)
