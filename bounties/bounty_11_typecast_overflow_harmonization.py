"""
Production Reference Solution for Tenstorrent tt-metal Issue #55325:
[Bounty] ttnn.typecast saturates narrowing to uint16 but wraps narrowing to uint8.

Target: tenstorrent/tt-metal #55325

Problem:
`ttnn.typecast` applied two conflicting overflow semantics inside the same operator:
- uint32 -> uint8 wrapped modulo 256 (`x & 0xFF`), matching PyTorch.
- uint32 -> uint16 saturated at 65535 (`min(x, 65535)`), violating PyTorch standard.
This inconsistency broke model graph compilation and caused silent numerical divergence
when casting weight tensors and index buffers on Blackhole (ttsim).

Solution:
1. Harmonize uint16 narrowing to follow standard modular wrapping by default:
   `output = input & 0xFFFF` (modulo 65536), matching PyTorch `tensor.to(torch.uint16)`.
2. Provide an explicit `saturate: bool = False` parameter allowing opt-in clamping
   where saturation is explicitly required by custom hardware kernels.
"""

from typing import Union, Optional
import numpy as np


def typecast_narrow_scalar(val: int, target_dtype: str = "uint16", saturate: bool = False) -> int:
    """
    Scalar typecasting with configurable overflow semantics.
    Defaults to wrapping (matching PyTorch).
    """
    if target_dtype.lower() == "uint8":
        limit = 256
        max_val = 255
    elif target_dtype.lower() == "uint16":
        limit = 65536
        max_val = 65535
    else:
        raise ValueError(f"Unsupported narrowing target: {target_dtype}")

    if saturate:
        return min(max_val, max(0, val))
    return val % limit


def typecast_narrow(
    tensor: np.ndarray,
    target_dtype: str = "uint16",
    saturate: bool = False
) -> np.ndarray:
    """
    Vectorized typecast narrowing from uint32/int32 to uint16 or uint8.
    Default behavior strictly matches PyTorch wrapping semantics.
    """
    arr = np.asarray(tensor)

    if target_dtype.lower() == "uint8":
        if saturate:
            return np.clip(arr, 0, 255).astype(np.uint8)
        # Standard PyTorch wrap: modulo 256
        return arr.astype(np.uint8)

    elif target_dtype.lower() == "uint16":
        if saturate:
            return np.clip(arr, 0, 65535).astype(np.uint16)
        # Harmonized PyTorch wrap: modulo 65536
        return arr.astype(np.uint16)

    raise ValueError(f"Unsupported narrowing target: {target_dtype}")
