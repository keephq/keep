<div align="center">
    <img src="/assets/keep.png?raw=true" width="86">
</div>

<h1 align="center">The Open-Source Alert Management and AIOps Platform</h1>

<div align="center">
    A single pane of glass for alert management, featuring filtering, bi-directional integrations, alert correlation, workflows, enrichment, and dashboards. 
    <br>AI correlation and AI summarization are currently in limited preview. (<a href="https://www.keephq.dev/meet-keep">Book a Demo</a>)
</div>
<br>

<div align="center">
    <a href="https://slack.keephq.dev">
        <img src="https://img.shields.io/badge/Join-important.svg?color=4A154B&label=Slack&logo=slack&labelColor=334155&logoColor=f5f5f5" alt="Join Slack" />
    </a>
    <a href="https://codecov.io/gh/keephq/keep">
        <img src="https://codecov.io/gh/keephq/keep/branch/main/graph/badge.svg?token=2VT6XYMRGS"/>
    </a>
</div>

<p align="center">
    <a href="#why-keep">Why Keep?</a> · 
    <a href="#getting-started">Getting Started</a> · 
    <a href="#supported-providers">Supported Tools and Integrations</a> · 
    <a href="https://docs.keephq.dev">Documentation</a> · 
    <a href="https://platform.keephq.dev">Try it Out</a> · 
    <a href="https://keephq.dev">Website</a> · 
    <a href="https://github.com/keephq/keep/issues/new?assignees=&labels=bug&template=bug_report.md&title=">Report a Bug</a> · 
    <a href="https://slack.keephq.dev">Join the Slack Community</a>
</p>

## How Does It Work?

1. **Connect Your Tools**: Integrate everything from monitoring platforms to databases and ticketing systems.

<div align="center">

| Connect Providers | Receive Alerts |
|-------------------|-----------------|
| <img src="/assets/connect_providers.gif" alt="Connect Providers" /> | <img src="/assets/view_alerts.gif" alt="View Alerts" /> |

</div>

2. **Set Up Workflows**: Initiate automated workflows in response to alerts or at custom intervals.

<div align="center">
| Create and Upload Workflows |
|-----------------------------|
| <img src="/assets/upload_workflow.gif" alt="Upload Workflows" /> |
</div>

3. **Enhance Operational Efficiency**: Automate alert handling to focus your team's efforts on what truly matters.

## Why Keep?

1. **Centralized Dashboard**: Manage all your alerts across various platforms from a single interface.
2. **Noise Reduction**: Deduplicate and correlate alerts to minimize alert fatigue.
3. **Automation**: Trigger workflows for alert enrichment and responses.
4. **Developer-First**: Keep is API-first, allowing you to manage workflows as code.
5. **Broad Compatibility**: Supports a wide range of [providers](#supported-providers) with more on the way.

## Workflows

Think of Workflows in Keep like GitHub Actions. Each Workflow is a declarative YAML file composed of triggers, steps, and actions to manage, enrich, and automate responses to alerts:

```yaml
workflow:
  id: most-basic-keep-workflow
  description: Send a Slack message when a CloudWatch alarm is triggered
  triggers:
    - type: alert
      filters:
        - key: source
          value: cloudwatch
    - type: manual
  steps:
    - name: Enrich alert with additional data from a database
      provider:
        type: bigquery
        config: "{{ providers.bigquery-prod }}"
        with:
          query: "SELECT customer_id, customer_type FROM `customers_prod` LIMIT 1"
  actions:
    - name: Trigger Slack Notification
      provider:
        type: slack
        config: "{{ providers.slack-prod }}"
        with:
          message: "Got alarm from AWS CloudWatch! {{ alert.name }}"
Workflow triggers can be executed manually or run at predefined intervals. More examples can be found here.

Supported Providers
Missing a provider? Submit a new provider issue and we’ll add it in no time!

Observability Tools
<div align="center"> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/newrelic-icon.png?raw=true" alt="New Relic" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/appdynamics-icon.png?raw=true" alt="AppDynamics" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/datadog-icon.png?raw=true" alt="Datadog" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/cloudwatch-icon.png?raw=true" alt="CloudWatch" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/elastic-icon.png?raw=true" alt="Elastic" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/grafana-icon.png?raw=true" alt="Grafana" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/prometheus-icon.png?raw=true" alt="Prometheus" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/sumologic-icon.png?raw=true" alt="Sumo Logic" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/victoriametrics-icon.png?raw=true" alt="VictoriaMetrics" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/zabbix-icon.png?raw=true" alt="Zabbix" /> </div>
Databases and Data Warehouses
<div align="center"> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/bigquery-icon.png?raw=true" alt="BigQuery" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/mysql-icon.png?raw=true" alt="MySQL" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/postgres-icon.png?raw=true" alt="PostgreSQL" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/snowflake-icon.png?raw=true" alt="Snowflake" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/clickhouse-icon.png?raw=true" alt="ClickHouse" /> </div>
Communication Platforms
<div align="center"> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/slack-icon.png?raw=true" alt="Slack" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/teams-icon.png?raw=true" alt="Microsoft Teams" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/telegram-icon.png?raw=true" alt="Telegram" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/pushover-icon.png?raw=true" alt="Pushover" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/resend-icon.png?raw=true" alt="Resend" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/mailchimp-icon.png?raw=true" alt="Mailchimp" /> <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/discord-icon.png?raw=true" alt="Discord" /> </div> ```
Just replace the current content in your README file with this code. Let me know if you need any further assistance!
## Getting Started
### Overview
Keep composed of three main components:
1. [Keep UI](https://github.com/keephq/keep/tree/main/keep-ui) - A NextJS app to connect your providers, centralize alerts and create the workflows.
2. [Keep Backend](https://github.com/keephq/keep/tree/main/keep) - A FastAPI server that implements the business logic behind Keep, including integrating with the tools, working with alerts and scheduling and running the workflows.
3. [Keep CLI](https://github.com/keephq/keep/blob/main/keep/cli/cli.py) - A CLI that lets you control and manage Keep via CLI.

>**Disclaimer**: we use [PostHog](https://posthog.com/faq) to collect anonymous telemetries to better learn how users use Keep (masked screen recordings for CLI commands)
To turn PostHog off, set the `DISABLE_POSTHOG=true` environment variable and remove the `NEXT_PUBLIC_POSTHOG_KEY` environment variable.

### Quickstart
#### Spinning up Keep with docker-compose
The easiest way to start with Keep is to run it via docker-compose:
```shell
curl https://raw.githubusercontent.com/keephq/keep/main/start.sh | sh
```
The UI is now available at http://localhost:3000 and the backend is available at http://localhost:8080.

#### Spinning up Keep with Helm on Kubernetes/Openshift
To install Keep to your Kubernetes ease free with Helm, run the following commands:

```shell
helm repo add keephq https://keephq.github.io/helm-charts
helm pull keephq/keep
helm install keep keephq/keep
```

More information about the Helm chart can be found [here](https://github.com/keephq/helm-charts).

#### Local development
You can also start Keep within your favorite IDE, e.g. [VSCode](https://docs.keephq.dev/development/getting-started#vscode)

#### Wanna get Keep up and running in production? Go through our detailed [development guide](https://docs.keephq.dev/development)

## 🫵 Keepers

### Top Contributors
A special thanks to our top contributors who help us make Keep great. You are more than awesome!

- [Furkan](https://github.com/pehlicd)
- [Asharon](https://github.com/asharonbaltazar)

Want to become a top contributor? Join our Slack and DM Tal, Shahar, or Furkan.

### Contributors
Thank you for contributing and continuously making <b>Keep</b> better, <b>you're awesome</b> 🫶

<a href="https://github.com/keephq/keep/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=keephq/keep" />
</a>
