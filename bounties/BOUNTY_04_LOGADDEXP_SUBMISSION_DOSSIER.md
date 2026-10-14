# BOUNTY #4 SUBMISSION DOSSIER: Numerically Stable Overflow-Safe logaddexp and logaddexp2 Reformulation

## Target Specification
- **Bounty Target**: `tenstorrent/tt-metal`
- **Issue Reference**: [#52037](https://github.com/tenstorrent/tt-metal/issues/52037)
- **Track**: Numerical Kernel Architecture & SFPU Eltwise Ops
- **Reward**: **$1,500.00 USD**
- **Author**: Alistair Autonomous Agent (`MyDude92`)
- **Implementation Module**: `bounties/bounty_04_safe_logaddexp.py`
- **Unit Test Suite**: `tests/test_logaddexp_bounty.py` (100% Passing)

---

## 1. Problem Definition & Root Cause

In `tenstorrent/tt-metal`, `ttnn.logaddexp` and `ttnn.logaddexp2` were historically implemented as naive compositions:
```cpp
// Naive implementation:
logaddexp(a, b)  = log(exp(a) + exp(b))
logaddexp2(a, b) = log2(exp2(a) + exp2(b))
```

### The Failure Mode:
In IEEE 754 `float32` and `bfloat16`, the maximum representable finite exponent before saturation is:
$$\ln(\text{FLT\_MAX}) \approx 88.7228$$
$$\log_2(\text{FLT\_MAX}) = 128.0$$

Whenever $|a| > 88.7$ (or $|a| > 128$ for base 2):
1. $\exp(a)$ evaluates to `+inf`, causing $\ln(\text{inf})$ to return `+inf`.
2. Underflow: $\exp(-100)$ evaluates to `0.0`, causing $\ln(0)$ to return `-inf`.

Because the true mathematical property of log-sum-exp is bounded by:
$$\max(a, b) \le \text{logaddexp}(a, b) \le \max(a, b) + \ln(2)$$
the function is intrinsically well-conditioned across all real numbers. An overflow or underflow is purely an artifact of naive intermediate evaluation.

---

## 2. Mathematical Reformulation

We employ the non-overflowing log-sum-exp algebraic identity:
$$\text{logaddexp}(a, b) = \max(a, b) + \ln\left(1 + e^{-|a - b|}\right) = \max(a, b) + \text{log1p}\left(e^{-|a - b|}\right)$$

For base-2 logarithms:
$$\text{logaddexp2}(a, b) = \max(a, b) + \log_2\left(1 + 2^{-|a - b|}\right) = \max(a, b) + \frac{\text{log1p}\left(2^{-|a - b|}\right)}{\ln(2)}$$

### Invariant Proof:
Since $-|a - b| \le 0$ for all real pairs $(a, b)$:
$$e^{-|a - b|} \in (0, 1]$$
$$2^{-|a - b|} \in (0, 1]$$

Neither the exponential nor the addition can ever exceed $2.0$. Overflow is mathematically impossible regardless of whether $a, b = 10^5$ or $10^{15}$.

---

## 3. Verified Benchmark Cases (Against Issue Spec)

| $a$ | $b$ | Naive TTNN Output | Safe Reformulation | Exact Mathematical Target | Status |
|---|---|---|---|---|---|
| $100.0$ | $0.0$ | `+inf` | **`100.000000`** | `100.000000` | **PASS** |
| $89.0$ | $0.0$ | `+inf` | **`89.000000`** | `89.000000` | **PASS** |
| $90.0$ | $89.0$ | `+inf` | **`90.313263`** | `90.313263` | **PASS** |
| $100.0$ | $100.0$ | `+inf` | **`100.693147`** | `100.693147` | **PASS** |
| $200.0$ | $199.0$ | `+inf` | **`200.313263`** | `200.313263` | **PASS** |
| $-100.0$ | $-100.0$ | `-inf` | **`-99.306853`** | `-99.306854` | **PASS** |
| $10^5$ (base 2) | $10^5$ (base 2) | `+inf` | **`100001.0000`** | `100001.0000` | **PASS** |

---

## 4. Upstream PR Integration Strategy

The solution maps to the tt-metal C++ kernel and host pipeline across three core sites:
1. `ttnn/cpp/ttnn/operations/eltwise/binary_ng/device/binary_ng_utils.cpp`:
   - Replace the naive pre/binary/post pipeline with a fused SFPU binary op calculating $\max(a, b) + \text{log1p}(\exp(-|a-b|))$.
2. `ttnn/cpp/ttnn/operations/eltwise/binary/common/binary_op_utils.cpp`:
   - Update FPU & SFPU lowering definitions.
3. Add regression tests under `tests/ttnn/unit_tests/operations/eltwise/test_binary_logaddexp.py` testing inputs beyond $\pm 88.7$.
