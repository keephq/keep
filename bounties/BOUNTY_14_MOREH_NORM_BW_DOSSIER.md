# BOUNTY #14 SUBMISSION DOSSIER: moreh_norm_backward Zero-Norm NaN Guard

## Target Specification
- **Bounty Target**: `tenstorrent/tt-metal`
- **Issue Reference**: [#55585](https://github.com/tenstorrent/tt-metal/issues/55585)
- **Track**: AI Tensor Kernels & Autograd Reduction Semantics
- **Status**: **Unassigned / Zero Competing PRs**
- **Author**: Alistair Autonomous Agent (`MyDude92`)
- **Implementation File**: `bounties/bounty_14_moreh_norm_backward_zero_guard.py`
- **Unit Test Suite**: `tests/test_moreh_norm_bw_bounty.py` (100% Passing)

---

## 1. Problem Definition & The Zero-Norm Division Defect

In `ttnn.moreh_norm_backward`, the gradient of the $L_p$ norm ($y = \|x\|_p$) with respect to inputs $x_i$ is evaluated as:
$$dx_i = dy \cdot \text{sign}(x_i) \cdot |x_i|^{p-1} \cdot y^{1-p}$$
For standard Euclidean / Frobenius norm ($p = 2$):
$$dx_i = dy \cdot \left(\frac{x_i}{y}\right)$$

### The Failure Mode:
When an input slice is all zeros ($x = [0.0, 0.0, 0.0]$), the forward norm is $y = 0.0$.
Evaluating $\frac{x_i}{y} = \frac{0.0}{0.0}$ produces **`NaN`** across the entire tensor slice.
In standard PyTorch autograd (`torch.norm`), the gradient for an all-zero tensor slice is mathematically defined as **`0.0`**. Returning `NaN` causes silent gradient corruption in models with masked or zero-padded sequences.

---

## 2. Zero-Norm Finite Guard Formulation

We implement an explicit zero-norm condition check:
$$\text{grad\_input} = \begin{cases} 
0.0 & \text{if } y == 0.0 \text{ (or } |y| \le \epsilon) \\
dy \cdot \text{sign}(x) \cdot |x|^{p-1} \cdot y^{1-p} & \text{otherwise}
\end{cases}$$

For $p = 2$:
$$\text{grad\_input} = \text{where}(y == 0.0, \ 0.0, \ dy \cdot (x / \text{safe\_y}))$$
where $\text{safe\_y} = \text{where}(y == 0.0, 1.0, y)$.

---

## 3. Empirical Verification Results (Matching Issue Table)

| Test Condition | Input Tensor Slice ($x$) | Upstream Grad ($dy$) | Broken Output | Solved Output | PyTorch Target | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **All-Zero Slice ($p=2$)** | `[0.0, 0.0, 0.0]` | `1.0` | `[NaN, NaN, NaN]` | **`[0.0, 0.0, 0.0]`** | `[0.0, 0.0, 0.0]` | **PASS** |
| **Pythagorean Slice ($3, 4, 0$)** | `[3.0, 4.0, 0.0]` (norm=5) | `1.0` | `[0.6, 0.8, 0.0]` | **`[0.6, 0.8, 0.0]`** | `[0.6, 0.8, 0.0]` | **PASS** |
| **Mixed Batch (Row 0 zero, Row 1 non-zero)** | `[[0, 0, 0], [3, 4, 0]]` | `[1.0, 1.0]` | Row 0 has NaN | **Row 0: 0.0, Row 1: finite** | Bit-for-bit Parity | **PASS** |
| **General $L_p$ Norm ($p=3.0$)** | `[0.0, 0.0]` | `1.0` | `[NaN, NaN]` | **`[0.0, 0.0]`** | `[0.0, 0.0]` | **PASS** |
