---
sidebar_label: len
---

# len(iterable)

### Input
An iterable.

### Output
Integer. The length of the iterable.

### Example
```yaml
condition:
-   type: threshold
    value:  "keep.len({{ steps.db-no-space.results }})"
    compare_to: 10
```
