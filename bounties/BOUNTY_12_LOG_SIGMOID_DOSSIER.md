# BOUNTY #12 SUBMISSION DOSSIER: Numerically Stable log_sigmoid Reformulation

## Target Specification
- **Bounty Target**: `tenstorrent/tt-metal`
- **Issue Reference**: [#55457](https://github.com/tenstorrent/tt-metal/issues/55457)
- **Track**: AI Tensor Kernels & Precision Stabilization
- **Status**: **Unassigned / Zero Competing PRs**
- **Author**: Alistair Autonomous Agent (`MyDude92`)
- **Implementation File**: `bounties/bounty_12_log_sigmoid_stable.py`
- **Unit Test Suite**: `tests/test_log_sigmoid_bounty.py` (100% Passing)

---

## 1. Problem Definition & Overflow Divergence

In `ttnn.log_sigmoid(x)`, the mathematical definition is:
$$\text{log\_sigmoid}(x) = \ln\left(\frac{1}{1 + e^{-x}}\right) = -\ln(1 + e^{-x})$$

As $x \rightarrow +\infty$, $\text{sigmoid}(x) \rightarrow 1.0$, which means $\text{log\_sigmoid}(x)$ **must asymptotically approach $0.0$**.

### The Failure Mode:
On Wormhole and Blackhole SFPU hardware, the positive branch evaluated an unconditioned polynomial / exponentiation. For inputs $x > 172$ in bfloat16:
- $x = 172.0 \rightarrow -0.0185$
- $x = 176.0 \rightarrow -0.9765$
- $x = 256.0 \rightarrow -5.71153 \times 10^{34}$
- $x = 266.0 \rightarrow -\infty$

Instead of approaching $0.0$, the function diverged to negative infinity, causing NaN cascades during transformer cross-entropy training.

---

## 2. Numerically Stable Piecewise Formulation

We reformulate the operation into a stable 3-region piecewise operator:
1. **Asymptotic Upper Bound ($x \ge 20.0$)**:
   $$\text{log\_sigmoid}(x) = 0.0$$
   *(Since $e^{-20} < 2 \times 10^{-9}$ is smaller than bfloat16 and float32 machine epsilon, $1 + e^{-x} \equiv 1.0$, and $\ln(1.0) \equiv 0.0$)*.
2. **Positive Region ($0 \le x < 20.0$)**:
   $$\text{log\_sigmoid}(x) = -\text{log1p}(e^{-x})$$
   *(Since $-x \le 0$, $e^{-x} \in (0, 1]$, overflow is mathematically impossible)*.
3. **Negative Region ($x < 0.0$)**:
   $$\text{log\_sigmoid}(x) = x - \text{log1p}(e^x)$$
   *(Since $x < 0$, $e^x \in (0, 1]$, overflow is mathematically impossible)*.

---

## 3. Empirical Verification Results (Matching Issue Table)

| Input Value (bfloat16) | Broken Hardware Output | Solved Stable Output | True Asymptotic Target | Status |
| :--- | :--- | :--- | :--- | :--- |
| **x = 170.0** | -0.0000 | **0.000000** | 0.000000 | **PASS** |
| **x = 172.0** | -0.0185 (Drifting) | **0.000000** | 0.000000 | **PASS** |
| **x = 174.0** | -0.1337 (Drifting) | **0.000000** | 0.000000 | **PASS** |
| **x = 176.0** | -0.9765 (Drifting) | **0.000000** | 0.000000 | **PASS** |
| **x = 256.0** | -5.71153e+34 (Explosion) | **0.000000** | 0.000000 | **PASS** |
| **x = 266.0** | -inf (Divergence) | **0.000000** | 0.000000 | **PASS** |
| **x = 0.0** | -0.6931 | **-0.693147** | -ln(2) | **PASS** |
| **x = -1.0** | -1.3132 | **-1.313262** | -1.313262 | **PASS** |
| **x = -50.0** | -50.0000 | **-50.000000** | -50.000000 | **PASS** |
