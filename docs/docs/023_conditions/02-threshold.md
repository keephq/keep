---
sidebar_label: threshold
---

# 🎯 Threshold

### The threshold condition compare between two values, and returns positive (True) if applied.
```yaml
-   type: threshold
    name: OPTIONAL (default "threshold")
    value:  REQUIRED. Left side of the comparison.
    compare_to: REQUIRED. Right side of the comparison.
    compare_type: OPTIONAL ("lt" or "gt". default is "gt")
```
### Example
```yaml
condition:
-   type: threshold
    value:  "{{ steps.db-no-space.results }}"
    compare_to: 10
```
* If `db-no-space` step returns 11 => `value` > 10 => the conditions returns *True*
* If `db-no-space` step returns 9.6 => `value` < 10 => the conditions returns *False*
