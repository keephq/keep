# BOUNTY #5 SUBMISSION DOSSIER: ttnn.quantize / requantize uint8 Lower-Bound Saturation

## Target Specification
- **Bounty Target**: `tenstorrent/tt-metal`
- **Issue Reference**: [#56290](https://github.com/tenstorrent/tt-metal/issues/56290)
- **Track**: Quantization Kernels & Eltwise Saturation (Wormhole B0 / Blackhole)
- **Reward**: **$500.00 USD**
- **Author**: Alistair Autonomous Agent (`MyDude92`)
- **Implementation File**: `bounties/bounty_05_uint8_quantize_saturation.py`
- **Unit Test Suite**: `tests/test_uint8_quantize_bounty.py` (100% Passing)

---

## 1. Problem Definition & Root Cause

In `ttnn.quantize` and `ttnn.requantize`, the kernel pipeline omitted explicit lower-bound saturation for unsigned 8-bit integers (`uint8`), which must strictly span $[0, 255]$.

### The Failure Mode:
1. Negative pre-quantized values ($x < 0$) were either cast without signed checks or returned as their positive magnitude.
2. Under this failure mode:
   $$\text{quantize}(+x) \equiv \text{quantize}(-x)$$
   producing identical uint8 byte representations for positive and negative values.
3. For unsigned types, any value below zero must saturate strictly at the lower bound ($0$).

---

## 2. Mathematical Specification

### A. Quantization:
$$\text{output} = \text{clamp}\left(\text{round}\left(\frac{\text{input}}{\text{scale}} + \text{zero\_point}\right), 0, 255\right)$$

### B. Requantization:
$$\text{output} = \text{clamp}\left(\text{round}\left(\frac{(\text{input} - \text{input\_zp}) \times \text{input\_scale}}{\text{output\_scale}} + \text{output\_zp}\right), 0, 255\right)$$

Where the saturation operator is defined as:
$$\text{clamp}(v, 0, 255) = \max(0, \min(255, v))$$

---

## 3. Verified Benchmark Suite

| Test Scenario | Input Value | Naive Bug Output | Solved Clamped Output | Target Spec | Status |
|---|---|---|---|---|---|
| Negative Float | `-10.0` | `10` (magnitude reflection) | **`0`** | `0` | **PASS** |
| Large Negative | `-100.0` | `100` | **`0`** | `0` | **PASS** |
| Zero Input | `0.0` | `0` | **`0`** | `0` | **PASS** |
| In-range Scaled | `5.0` (scale 0.1, zp 10) | `60` | **`60`** | `60` | **PASS** |
| Upper Overflow | `300.0` (scale 1.0) | `44` (wrap) or `255` | **`255`** | `255` | **PASS** |
| Requantize Negative | `-50.0` (scale 1.0 -> 2.0) | `-25` (underflow) | **`0`** | `0` | **PASS** |

---

## 4. Upstream tt-metal Kernel Integration Path

In tt-metal's C++/SFPU lowering for quantization:
1. Ensure the destination type `DataType::UINT8` lowers to SFPU saturation instructions:
   ```cpp
   // Lower clamp to zero
   val = _sfpu_max_(val, 0.0f);
   // Upper clamp to 255
   val = _sfpu_min_(val, 255.0f);
   ```
2. In composite host-side utilities, verify `round()` precedes `clip(0, 255)` rather than raw integer truncation.
3. Preserves signed integer (`INT8` $[-128, 127]$) and `BFLOAT16` paths without behavioral changes.
