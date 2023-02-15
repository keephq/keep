---
sidebar_label: High Level Architecture
sidebar_position: 3
---

# High Level Architecture 👨🏻‍💻
![Alt bla](arch.png?raw=true "HL Architecture")

### Alert
An alert is a notification that is triggered when a specific condition or set of conditions is met. Alerts are used to notify stakeholders or teams about potential issues, anomalies or abnormal behavior in systems or applications.

When an alert is triggered, it typically includes relevant information about the issue, such as the type of problem, its severity, and the location of the problem. The notification is sent to the relevant stakeholders, such as system administrators, developers, or support teams, who can then investigate and take action to resolve the issue.

Alerts can be triggered for a wide range of reasons, including system failures, performance degradation, security breaches, and other types of issues that can affect the availability or performance of a system or application. Effective alerting is an essential component of a comprehensive monitoring strategy, as it allows teams to detect and respond to issues quickly, minimizing the impact on users and business operations.

### Provider
An alert provider queries data from various sources, such as observability tools (Datadog, New Relic, etc), Cloud vendors (AWS, Google Cloud, etc), SQL databases (Postgres, Snowflake) and applies predefined rules or conditions to generate alerts.


### Step
Alerts in Keep are made up of one or more steps that being executed to decide if alert should be triggered or not.
Similar to the steps in GitHub Actions, Keep's steps are executed sequentially and are interdependent.
Each step can get data from some provider to enrich the context the alert has. For example, a first step can get data from Datadog, and the second step can enrich it with SQL query from another database.


### Condition
 An alert condition is a predefined rule or set of rules that define when an alert should be triggered. An alert condition typically consists of a specific event, threshold or set of criteria that must be met to trigger the alert. For example, an alert condition for a server could be a CPU usage percentage that exceeds a certain threshold or a website response time that is slower than a specific duration. When the defined conditions are met, an alert is triggered, and notifications are sent to the relevant stakeholders. Alert conditions are commonly used in monitoring systems to detect and notify on potential issues before they escalate.

### Context
Every step in Keep generates context, whether it's data from a provider, output from a condition, or an invoked action. This information is stored in the context manager and can be accessed from any point in the workflow. Read `Syntax` to better understand how to use context.
