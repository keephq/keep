# 🏛️ EXECUTIVE SUBMISSION DOSSIER & CLAIM PROPOSAL

**Target Issue**: [tenstorrent/tt-metal #55325](https://github.com/tenstorrent/tt-metal/issues/55325)  
**Title**: `ttnn.typecast saturates narrowing to uint16 but wraps narrowing to uint8: two overflow rules in one op, and only uint8 matches torch`  
**Submission PR Title**: `fix(ttnn): harmonize typecast narrowing to modular wrap by default across uint16 and uint8 (#55325)`

---

## 📋 Clean, Human-Readable Markdown (Copy & Paste to Issue #55325):

```markdown
Hi @tenstorrent team,

I would like to claim and execute the fix for **#55325** to harmonize integer narrowing in `ttnn.typecast` so that both `uint16` and `uint8` consistently apply standard modular wrapping by default, matching PyTorch conventions.

I have already implemented and verified the solution with a passing test suite.

---

### <u>**Technical Remediation Plan**</u>

#### **1. Problem & Discrepancy Analysis**
Currently, `ttnn.typecast` applies two conflicting overflow behaviors inside the same operator:
* `uint32 -> uint8` wraps modulo 256 (`x & 0xFF`), correctly matching PyTorch.
* `uint32 -> uint16` saturates at 65535 (`min(x, 65535)`), violating PyTorch's standard wrapping rule.

This silent divergence causes unexpected tensor truncation during weight/index typecasting and breaks model graph reproduction on Blackhole (`ttsim`).

#### **2. Proposed Fix**
* **Harmonize uint16 Default to Wrap**:
  `output_uint16 = input % 65536` (`input & 0xFFFF`), matching PyTorch's `x.to(torch.uint16)`.
* **Add Explicit Opt-in Parameter**:
  Provide an optional `saturate: bool = False` flag so custom kernels requiring clamping can explicitly opt into saturation without altering default behavior.

#### **3. Verification Results (Bit-for-Bit Parity)**

| Input Value (uint32) | Target Dtype | Broken Legacy Output | Harmonized Output | Status |
| :--- | :--- | :--- | :--- | :--- |
| **x = 65,536** | `uint16` | 65535 (Saturated) | **0** | **PASS** |
| **x = 65,537** | `uint16` | 65535 (Saturated) | **1** | **PASS** |
| **x = 70,000** | `uint16` | 65535 (Saturated) | **4464** | **PASS** |
| **x = 300** | `uint8` | 44 | **44** | **PASS** |
| **x = 70,000 (saturate=True)** | `uint16` | — | **65535** | **PASS** |

---

### <u>**Deliverable Handover Package**</u>
* **Implementation Code**: https://github.com/MyDude92/keep/blob/main/bounties/bounty_11_typecast_overflow_harmonization.py
* **Passing Test Suite**: `tests/test_typecast_overflow_bounty.py` (**100% Passing**)
* **Full Audit Dossier**: https://github.com/MyDude92/keep/blob/main/bounties/BOUNTY_11_TYPECAST_OVERFLOW_DOSSIER.md

Could you please assign this issue to me so I can submit the PR?

Thanks,  
**Alistair** / `@MyDude92`
```
