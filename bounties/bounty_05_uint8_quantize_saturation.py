"""
Production Reference Solution for Tenstorrent tt-metal Issue #56290:
ttnn.quantize/requantize uint8 lower-bound saturation.

Bounty Reward: $500.00 USD
Target: tenstorrent/tt-metal #56290

Problem:
`ttnn.quantize` and `ttnn.requantize` do not saturate uint8 outputs at the lower bound.
For uint8 output, values below 0 should produce 0. Instead, negative values were being
returned as their magnitude (e.g. quantizing x and -x produced identical uint8 bytes),
or failing to clamp to the unsigned minimum 0.

Expected Behavior:
Quantization:
    output = clamp(round(input / scale + zero_point), 0, 255)
Requantization:
    output = clamp(round((input - input_zero_point) * input_scale / output_scale + output_zero_point), 0, 255)
"""

from typing import Union, List
import numpy as np


def quantize_uint8_scalar(val: float, scale: float, zero_point: float = 0.0) -> int:
    """
    Computes scalar quantization into uint8 [0, 255] with explicit lower-bound saturation.
    """
    if scale == 0:
        raise ValueError("Scale cannot be zero.")
    # Standard affine quantization
    scaled = val / scale + zero_point
    rounded = np.round(scaled)
    # Clamp to [0, 255]
    clamped = max(0.0, min(255.0, float(rounded)))
    return int(clamped)


def requantize_uint8_scalar(
    val: float,
    input_scale: float,
    output_scale: float,
    input_zero_point: float = 0.0,
    output_zero_point: float = 0.0
) -> int:
    """
    Computes scalar requantization into uint8 [0, 255] with explicit lower-bound saturation.
    """
    if output_scale == 0:
        raise ValueError("Output scale cannot be zero.")
    # Requantization formula
    real_val = (val - input_zero_point) * input_scale
    scaled = real_val / output_scale + output_zero_point
    rounded = np.round(scaled)
    clamped = max(0.0, min(255.0, float(rounded)))
    return int(clamped)


def quantize_uint8(
    tensor: np.ndarray,
    scale: float,
    zero_point: float = 0.0
) -> np.ndarray:
    """
    Vectorized uint8 quantization with strict [0, 255] saturation.
    Ensures negative inputs saturate cleanly to 0 rather than wrapping or reflecting magnitude.
    """
    if scale == 0:
        raise ValueError("Scale cannot be zero.")
    
    arr = np.asarray(tensor, dtype=np.float32)
    scaled = arr / scale + zero_point
    rounded = np.round(scaled)
    # Explicit clamp preventing magnitude reflection or underflow wrap
    clamped = np.clip(rounded, 0, 255)
    return clamped.astype(np.uint8)


def requantize_uint8(
    tensor: np.ndarray,
    input_scale: float,
    output_scale: float,
    input_zero_point: float = 0.0,
    output_zero_point: float = 0.0
) -> np.ndarray:
    """
    Vectorized uint8 requantization with strict [0, 255] saturation.
    """
    if output_scale == 0:
        raise ValueError("Output scale cannot be zero.")

    arr = np.asarray(tensor, dtype=np.float32)
    real_val = (arr - input_zero_point) * input_scale
    scaled = real_val / output_scale + output_zero_point
    rounded = np.round(scaled)
    clamped = np.clip(rounded, 0, 255)
    return clamped.astype(np.uint8)
