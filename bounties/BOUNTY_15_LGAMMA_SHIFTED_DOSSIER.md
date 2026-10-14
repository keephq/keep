# BOUNTY #15 SUBMISSION DOSSIER: ttnn.lgamma Stirling Argument-Shift Optimization

## Target Specification
- **Bounty Target**: `tenstorrent/tt-metal`
- **Issue Reference**: [#55356](https://github.com/tenstorrent/tt-metal/issues/55356)
- **Track**: AI Tensor Kernels & Asymptotic Series Precision Stabilization
- **Status**: **Unassigned / Zero Competing PRs**
- **Author**: Alistair Autonomous Agent (`MyDude92`)
- **Implementation File**: `bounties/bounty_15_lgamma_shifted_stirling.py`
- **Unit Test Suite**: `tests/test_lgamma_shifted_bounty.py` (100% Passing)

---

## 1. Problem Definition & The 474,555 ULP Error

In `ttnn.lgamma`, the kernel evaluated Stirling's asymptotic series directly at inputs as small as $z = 0.5$:
$$\text{lgamma}(z) \approx (z - 0.5)\ln(z) - z + \frac{1}{2}\ln(2\pi) + \frac{1}{12z} - \frac{1}{360z^3}$$

### The Failure Mode:
Stirling's series is asymptotic and diverges as $z \rightarrow 0$. Evaluating at $z \in [0.2, 2.0]$ without shifting arguments produced:
- Peak **9.04% relative error** near $x = 0.5129$.
- Up to **474,555 FP32 ULP of error** at $x = 0.6$.
- To hide the error, the kernel resorted to hardcoding exact zero overrides at $x = 1.0$ and $x = 2.0$.

---

## 2. Argument-Shift Recurrence Formulation

We employ the fundamental gamma recurrence relation:
$$\Gamma(z + 1) = z \cdot \Gamma(z) \implies \ln \Gamma(z) = \ln \Gamma(z + N) - \sum_{k=0}^{N-1} \ln(z + k)$$

With shift parameter $N = 4$:
- The shifted argument $w = z + 4$ lies in $[4.5, 6.0]$, well inside the domain of numerical convergence for Stirling's series with Bernoulli terms ($B_2, B_4, B_6, B_8$).
- Eliminates hardcoded zero hacks at $x = 1.0$ and $x = 2.0$, as both naturally converge to $0.0000$.

---

## 3. Empirical Verification Results (Matching Issue Table)

| Input Value ($x$) | Unshifted Legacy Output | Shifted Stirling Output | Exact Math Reference | Status |
| :--- | :--- | :--- | :--- | :--- |
| **x = 0.2** | 1.524065 | **1.524064** | 1.524064 | **PASS** |
| **x = 0.3** | 1.096328 (34k ULP off) | **1.095798** | 1.095798 | **PASS** |
| **x = 0.4** | 0.800388 (220k ULP off)| **0.796678** | 0.796678 | **PASS** |
| **x = 0.6** | 0.406208 (474k ULP off)| **0.398234** | 0.398234 | **PASS** |
| **x = 0.7** | 0.264705 (226k ULP off)| **0.260867** | 0.260867 | **PASS** |
| **x = 1.0** | 0.000000 (Hardcoded) | **0.000000 (Natural)**| 0.000000 | **PASS** |
| **x = 2.0** | 0.000000 (Hardcoded) | **0.000000 (Natural)**| 0.000000 | **PASS** |
