---
sidebar_label: Syntax
sidebar_position: 4
---

# Basic Syntax

#### At Keep, we view alerts as workflows, which consist of a series of steps executed in sequence, each with its own specific input and output. To keep our approach simple, Keep's syntax is designed to closely resemble the syntax used in GitHub Actions. We believe that GitHub Actions has a well-established syntax, and there is no need to reinvent the wheel.

## Full Example
```yaml
alert:
  id: raw-sql-query
  description: Monitor that time difference is no more than 1 hour
  steps:
    - name: get-max-datetime
      provider:
        type: mysql
        config: "{{ providers.mysql-prod }}"
        with:
          # Get max(datetime) from the random table
          query: "SELECT MAX(datetime) FROM demo_table LIMIT 1"
      condition:
      - type: threshold
        # datetime_compare(t1, t2) compares t1-t2 and returns the diff in hours
        #   utcnow() returns the local machine datetime in UTC
        #   to_utc() converts a datetime to UTC
        value: datetime_compare(utcnow(), to_utc({{ steps.this.results[0][0] }}))
        compare_to: 1 # hours
        compare_type: gt # greater than
  actions:
    - name: trigger-slack
      provider:
        type: slack
        config: " {{ providers.slack-demo }} "
        with:
          message: "DB datetime value ({{ steps.get-max-datetime.conditions.threshold[0].value }}) is greater than 1! 🚨"
```

### Now, let's break it down! 🔨
### Alert
```yaml
alert:
  id: raw-sql-query
  description: Monitor that time difference is no more than 1 hour
  steps:
    -
  actions:
    -
```

`Alert` is built of:
- Metadata (id, description. owners and tags will be added soon)
- `steps` - list of steps
- `actions` - list of actions

### Steps
```yaml
steps:
    - name: get-max-datetime
      provider:
      condition:
```
`Step` is built of:
  - `name` - the step name (context will be accessible through `{{ steps.name.results }}`).
  - `provider` - the data source.
  - `conditions` - zero (or more) conditions that runs after the `provider` provided the data.

### Provider
```yaml
provider:
    type: mysql
    config: "{{ providers.mysql-prod }}"
    with:
        # Get max(datetime) from the random table
        query: "SELECT MAX(datetime) FROM demo_table LIMIT 1"
```
`Provider` is built of:
- `type` - the type of the provider ([see supported providers](providers/getting-started.md))
- `config` - the provider configuration. you can either supply it explicitly or using `"{{ providers.mysql-prod }}"`
- `with` - all type-specific provider configuration. for example, for `mysql` we will provide the SQL query.

### Condition
```yaml
condition:
- type: threshold
    # datetime_compare(t1, t2) compares t1-t2 and returns the diff in hours
    #   utcnow() returns the local machine datetime in UTC
    #   to_utc() converts a datetime to UTC
    value: datetime_compare(utcnow(), to_utc({{ steps.this.results[0][0] }}))
    compare_to: 1 # hours
    compare_type: gt # greater than
```
`Condition` is built of:
- `type` - the type of the condition
- `value` - the value that will be supplied to the condition during the alert execution
- `compare_to` - whats `value` will be compared against
- `compare_type` - all type-specific condition configuration

### Actions
```yaml
actions:
- name: trigger-slack
  provider:
    type: slack
    config: " {{ providers.slack-demo }} "
    with:
       message: "DB datetime value ({{ steps.get-max-datetime.conditions.threshold[0].value }}) is greater than 1! 🚨"
```

#### * The last part of the alert are the actions.

`Action` is built of:
- `name` - the name of the action.
- `provider` - the provider that will trigger the action.

The `provider` configuration is already covered in [Providers](syntax#provider)
