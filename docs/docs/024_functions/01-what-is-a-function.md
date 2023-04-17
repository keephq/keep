---
sidebar_label: What is a function?
sidebar_position: 1
---


# What is a Function?
| :exclamation:  To use a keep function, prefix it with `keep.`, for example, use `keep.len` and not `len`  :exclamation: |
|-----------------------------------------|

In Keep's context, functions extend the power of context injection.

For example, if a step returns a list, you can use the `keep.len` function to use the number of results instead of the actual results.


```yaml
condition:
- type: threshold
  # Use the len of the results instead of the results
  value:  "keep.len({{ steps.db-no-space.results }})"
  compare_to: 10
```

### Current functions
1. [all](all)
2. [diff](diff)
3. [len](len)
4. [split](split)
5. [first](first)
6. [utcnow](utcnow)
7. [to_utc](to_utc)
8. [datetime_compare](datetime_compare)

### How to create a new function?

Keep functions designed to be extendible.

To create a new function, all you have to do is to add it to the [functions](https://github.com/keephq/keep/blob/main/keep/functions/__init__.py) directory.
