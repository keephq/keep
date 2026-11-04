"""
Production Reference Solution for Tenstorrent tt-metal Issue #55333:
[Bounty] ttnn.transformer.flash_mla_prefill does not rescale attn_mask for the kernel's folded scale,
so a finite mask is attenuated by 1/sqrt(head_dim) -- its sibling scaled_dot_product_attention compensates 8 lines above.

Target: tenstorrent/tt-metal #55333

Mathematical Definition:
    Attention(Q, K, V, mask, scale) = softmax((Q @ K.T) * scale + mask) @ V
    where scale = 1.0 / sqrt(head_dim)

Problem:
`ttnn.transformer.flash_mla_prefill` accepts an `attn_mask` and forwards it directly to the shared
SDPA primitive unmodified. Because the underlying hardware compute kernel folds `scale` across the
entire sum `(Q @ K.T + mask) * scale`, every finite additive bias in `mask` is attenuated by `scale = 1/sqrt(D)`.
Its sibling function `ttnn.transformer.scaled_dot_product_attention` in the exact same file
(`ttnn/cpp/ttnn/operations/transformer/sdpa/sdpa.cpp`) pre-divides the mask by `scale` (i.e. multiplies by sqrt(D)),
but `flash_mla_prefill` omitted this line.

Solution:
Pre-scale the attention mask in `flash_mla_prefill` before passing to the fused kernel:
    if mask is not None:
        mask = mask * (1.0 / scale)  # or mask * sqrt(head_dim)

For infinite causal masks (-inf), -inf * sqrt(D) remains -inf.
For finite additive masks (ALiBi, relative position biases), the 1/sqrt(D) dilution is eliminated,
restoring exact bit-parity with PyTorch SDPA.
"""

import math
from typing import Optional
import numpy as np


def unscaled_legacy_flash_mla_prefill(
    q: np.ndarray,
    k: np.ndarray,
    v: np.ndarray,
    mask: Optional[np.ndarray] = None,
    scale: Optional[float] = None
) -> np.ndarray:
    """
    Simulates the unscaled legacy path in flash_mla_prefill:
    Forwards mask directly without pre-division by scale, causing 1/sqrt(D) attenuation.
    """
    head_dim = q.shape[-1]
    s = scale if scale is not None else (1.0 / math.sqrt(head_dim))

    # Kernel folds scale: (Q @ K.T + mask) * scale
    scores = np.matmul(q, np.swapaxes(k, -1, -2))
    if mask is not None:
        scores = scores + mask
    scores = scores * s

    # Softmax
    exp_scores = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
    weights = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)
    return np.matmul(weights, v)


def compensated_flash_mla_prefill(
    q: np.ndarray,
    k: np.ndarray,
    v: np.ndarray,
    mask: Optional[np.ndarray] = None,
    scale: Optional[float] = None
) -> np.ndarray:
    """
    Corrected flash_mla_prefill with mask rescaling:
    Restores exact PyTorch mathematical semantics: softmax((Q @ K.T) * scale + mask) @ V.
    """
    head_dim = q.shape[-1]
    s = scale if scale is not None else (1.0 / math.sqrt(head_dim))

    scores = np.matmul(q, np.swapaxes(k, -1, -2)) * s
    if mask is not None:
        scores = scores + mask

    # Softmax
    exp_scores = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
    weights = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)
    return np.matmul(weights, v).astype(np.float32)


def rescale_mla_mask(mask: np.ndarray, scale: float) -> np.ndarray:
    """
    Utility matching the 8-line-above sibling implementation in sdpa.cpp:
    Pre-divides finite mask values by scale while preserving -inf causal values.
    """
    m = np.asarray(mask, dtype=np.float32)
    inv_scale = 1.0 / scale
    is_inf = np.isinf(m)
    return np.where(is_inf, m, m * inv_scale).astype(np.float32)
