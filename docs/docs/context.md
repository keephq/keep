---
sidebar_label: Context
sidebar_position: 5
---

# Working with Context
Keep uses [Mustache](https://mustache.github.io/) syntax to inject context at runtime, supporting functions, dictionaries, lists, and nested access. Here are some examples:
- {{ steps.step-id.results }} - Result of step-id
- len({{ steps.step-id.results }}) - Number of results from step-id
- {{ steps.this.results[0] }} - First result of this step
- first({{ steps.this.results }}) - First result (equivalent to the previous example)
- {{ steps.step-id.results[0][0] }} - First item of the first result

If you have suggestions/improvments for Keep's syntax, please [open feature request](https://github.com/keephq/keep/issues/new?assignees=&labels=&template=feature_request.md&title=) and get eternal glory.

### Special context
Keep provides two special context containers - `providers` and `steps`

#### Providers
Provider configuration typically look like:
```
provider:
  type: mysql
  config: "{{ providers.mysql-prod }}"
  with:
    # Get max(datetime) from the random table
    query: "SELECT MAX(datetime) FROM demo_table LIMIT 1"
```
Here, `{{ providers.mysql-prod }}` is dynamically translated at runtime from the providers.yaml file.

#### Steps
The output of steps can be accessed from anywhere in the YAML using `{{ steps.step-id.results }}`. This output can be used in conditions, actions, or any other place.



### Functions
Keep's syntax allow to use functions on context blocks. For example, `len({{ steps.step-id.results }})` will return the number of results of `step-id` step.

[To see supported functions](functions/what-is-a-function.md)
[To create new functions](functions/what-is-a-function.md)

Under the hood, Keep uses Python's `ast` module to parse these expressions and evaluate them as best as possible.
