---
sidebar_label: One Until Resolved
sidebar_position: 2
---

# 🎯 One Until Resolved

## Intro
The action will trigger once the alert is resolved.

For example:

1. Alert triggered -> Action triggered
2. Alert triggered again -> Action is not triggered
3. Alert resolved ->  Action is not triggered, since alert resolved
4. Alert triggered again -> Action is triggered

## How to use
Add the following attribute to your action:
```
throttle:
    type: one_until_resolved
```
For example:
```
# Database disk space is low (<10%)
alert:
  id: service-is-up
  description: Check that the service is up
  steps:
    - name: service-is-up
      provider:
        type: python
        with:
          # any external libraries needed
          imports: requests
          code: requests.get("http://localhost:3000")
      condition:
        - type: assert
          assert: "{{ steps.this.results.status_code }} == 200"
  actions:
    - name: trigger-slack
      throttle:
        type: one_until_resolved
```
