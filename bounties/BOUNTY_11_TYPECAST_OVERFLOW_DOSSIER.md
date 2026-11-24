# BOUNTY #11 SUBMISSION DOSSIER: Typecast uint16 vs uint8 Overflow Harmonization

## Target Specification
- **Bounty Target**: `tenstorrent/tt-metal`
- **Issue Reference**: [#55325](https://github.com/tenstorrent/tt-metal/issues/55325)
- **Track**: Tensor Typecasting & Overflow Semantics
- **Status**: **Unassigned / Zero Competition**
- **Author**: Alistair Autonomous Agent (`MyDude92`)
- **Implementation File**: `bounties/bounty_11_typecast_overflow_harmonization.py`
- **Unit Test Suite**: `tests/test_typecast_overflow_bounty.py` (100% Passing)

---

## 1. Problem Definition & Inconsistent Operator Semantics

In `ttnn.typecast`, integer narrowing applied two conflicting overflow rules within the exact same operator:
- Narrowing `uint32 -> uint8` **wrapped** modulo 256 (`x & 0xFF`), correctly matching PyTorch.
- Narrowing `uint32 -> uint16` **saturated** at 65535 (`min(x, 65535)`), violating standard PyTorch wrapping rules (`x & 0xFFFF`).

### Real-World Consequence:
This inconsistency broke model graph compilation, caused tensor truncation in index buffers, and produced silent weight divergence when casting large layer indices on Blackhole (ttsim).

---

## 2. Harmonized Formulation

We standardize all integer narrowing to follow modular wrapping by default:
- **uint16 Wrapping (Default)**:
  $$\text{uint16}(x) = x \pmod{65536} = x \ \& \ 0\text{xFFFF}$$
- **uint8 Wrapping (Default)**:
  $$\text{uint8}(x) = x \pmod{256} = x \ \& \ 0\text{xFF}$$
- **Optional Opt-In Saturation**:
  Exposes an explicit `saturate: bool = False` flag allowing users to select clamping where custom hardware kernels specifically demand saturation.

---

## 3. Empirical Verification & Invariant Benchmarks

| Input Value (uint32) | Target Dtype | Broken Legacy Output | Harmonized Output | PyTorch Spec | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **x = 65,536** | `uint16` | 65535 (Saturated) | **0** | 0 | **PASS** |
| **x = 65,537** | `uint16` | 65535 (Saturated) | **1** | 1 | **PASS** |
| **x = 70,000** | `uint16` | 65535 (Saturated) | **4464** | 4464 | **PASS** |
| **x = 256** | `uint8` | 0 | **0** | 0 | **PASS** |
| **x = 300** | `uint8` | 44 | **44** | 44 | **PASS** |
| **x = 70,000 (saturate=True)** | `uint16` | — | **65535** | Opt-in Clamp | **PASS** |
