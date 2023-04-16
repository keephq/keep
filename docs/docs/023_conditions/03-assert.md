---
sidebar_label: assert
---

# 🎯 Assert

### The assert condition implements the "python assert" behaviour
```yaml
-   type: assert
    name: OPTIONAL (default "assert")
    assert: REQUIRED. The assert expression to evaluate.
```
### Example
```yaml
condition:
- type: assert
  assert: "{{ steps.service-is-up.results.status_code }} == 200"
```
* If `steps.service-is-up.results.status_code` step returns 200 => `assert 200 == 200` => the conditions returns *False* (since the assert pass)
* If `steps.service-is-up.results.status_code` step returns 404 => `assert 404 == 200` => the conditions returns *True* (since the assert fails)
