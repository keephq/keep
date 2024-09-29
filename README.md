<div align="center">
    <img src="/assets/keep.png?raw=true" width="86">
</div>

<h1 align="center">Open-Source Alert Management and AIOps Platform</h1>

<p align="center">
    Centralized platform for managing alerts, workflows, integrations, dashboards, and AIOps features.
    <br>AI Correlation and Summarization features available in <strong>limited preview</strong> 
    (<a href="https://www.keephq.dev/meet-keep">Book a Demo</a>).
</p>

<div align="center">
    <a href="https://slack.keephq.dev">
        <img src="https://img.shields.io/badge/Join-Slack-important.svg?color=4A154B&logo=slack&labelColor=334155&logoColor=f5f5f5" alt="Join Slack" />
    </a>
    <a href="https://codecov.io/gh/keephq/keep">
        <img src="https://codecov.io/gh/keephq/keep/branch/main/graph/badge.svg?token=2VT6XYMRGS"/>
    </a>
</div>

<div align="center">
    <a href="#why-keep">Why Keep?</a> · 
    <a href="#getting-started">Getting Started</a> · 
    <a href="#supported-providers">Supported Providers</a> · 
    <a href="https://docs.keephq.dev">Docs</a> · 
    <a href="https://platform.keephq.dev">Try it out</a> · 
    <a href="https://keephq.dev">Website</a> · 
    <a href="https://github.com/keephq/keep/issues/new?assignees=&labels=bug&template=bug_report.md&title=">Report Bug</a> · 
    <a href="https://slack.keephq.dev">Slack Community</a>
</div>

<div align="center">
    <!-- <p>Create and Upload Workflows</p> -->
    <img src="/assets/Keep-landingPage.png" />
</div>

## How It Works

### 1. Connect Your Tools
Integrate everything from monitoring platforms to databases and ticketing systems to receive and manage alerts.

<div align="center">
    <table>
        <tr>
            <th>Connect Providers</th>
            <th>Receive Alerts</th>
        </tr>
        <tr>
            <td><img src="/assets/Connect_providers1.gif" /></td>
            <td><img src="/assets/View_alerts1.gif" /></td>
        </tr>
    </table>
</div>

### 2. Set Up Workflows
Define automated workflows that trigger responses to alerts or operate on custom intervals.

<div align="center">
    <p>Create and Upload Workflows</p>
    <img src="/assets/Upload_workflow1.gif" />
</div>

### 3. Enhance Operational Efficiency
Automate alert management to reduce manual handling, allowing teams to focus on high-priority issues.

---

## Why Choose Keep?

- **Centralized Dashboard**: Manage all alerts from multiple platforms through one unified interface.
- **Noise Reduction**: Deduplicate and correlate alerts to minimize alert fatigue.
- **Automation**: Trigger workflows to enrich alerts and automatically respond to incidents.
- **Developer-First Approach**: API-first design that supports managing workflows as code.
- **Integrations**: Seamless integration with numerous platforms and tools (see below).

---

## Workflows

Workflows in Keep are similar to GitHub Actions. They are declarative YAML files composed of triggers, steps, and actions that help automate and respond to alerts. Below is an example of a basic workflow:

```yaml
workflow:
  id: basic-slack-alert-workflow
  description: Send a Slack message when a CloudWatch alarm is triggered.
  triggers:
    - type: alert
      filters:
        - key: source
          value: cloudwatch
    - type: manual
  steps:
    - name: enrich-alert
      provider:
        type: bigquery
        config: "{{ providers.bigquery-prod }}"
        with:
          query: "SELECT customer_id FROM `customers_prod` LIMIT 1"
  actions:
    - name: send-slack-message
      provider:
        type: slack
        config: "{{ providers.slack-prod }}"
        with:
          message: "CloudWatch alarm triggered: {{ alert.name }}"
```
Workflow triggers can either be executed manually when an alert is activated or run at predefined intervals. More examples can be found [here](https://github.com/keephq/keep/tree/main/examples/workflows).

## Supported Providers
> Missing any? Just submit a [new provider issue](https://github.com/keephq/keep/issues/new?assignees=&labels=provider&projects=&template=new_provider_request.md&title=) and we will add it in the blink of an eye.

<h3 align="center">Observability tools</h3>
<p align="center">
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/newrelic-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/appdynamics-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/datadog-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/cloudwatch-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/elastic-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/grafana-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/prometheus-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/sumologic-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/victoriametrics-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/zabbix-icon.png?raw=true"/>
</p>
<p align="center">
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/sentry-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/dynatrace-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/signalfx-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/azuremonitoring-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/gcpmonitoring-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/splunk-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/incidentmanager-icon.png"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/coralogix-icon.png?raw=true" />
</p>
<h3 align="center">Databases and data warehouses</h3>
<p align="center">
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/bigquery-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/mysql-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/postgres-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/snowflake-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/clickhouse-icon.png?raw=true"/>
</p>
<h3 align="center">Communication platforms</h2>
<p align="center">
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/slack-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/teams-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/telegram-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/pushover-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/resend-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/mailchimp-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/discord-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/twilio-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/ntfy-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/sendgrid-icon.png?raw=true"/>
</p>
<h3 align="center">Incident Management tools</h2>
<p align="center">
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/pagerduty-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/pagertree-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/site24x7-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/opsgenie-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/zenduty-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/squadcast-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/grafana_oncall-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/openobserve-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/statuscake-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/uptimekuma-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/rollbar-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/centreon-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/netdata-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/incidentio-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/grafana_incident-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/webhook-icon.png?raw=true"/>
</p>
<h3 align="center">Ticketing tools</h2>
<p align="center">
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/jira-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/gitlab-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/redmine-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/trello-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/github-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/servicenow-icon.png?raw=true"/>
</p>
<h3 align="center">Container Orchestration platforms</h2>
<p align="center">
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/openshift-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/kubernetes-icon.png?raw=true"/>
</p>

## Getting Started
### Overview
Keep composed of three main components:
1. [Keep UI](https://github.com/keephq/keep/tree/main/keep-ui) - A NextJS app to connect your providers, centralize alerts and create the workflows.
2. [Keep Backend](https://github.com/keephq/keep/tree/main/keep) - A FastAPI server that implements the business logic behind Keep, including integrating with the tools, working with alerts and scheduling and running the workflows.
3. [Keep CLI](https://github.com/keephq/keep/blob/main/keep/cli/cli.py) - A CLI that lets you control and manage Keep via CLI.

>**Disclaimer**:  we use [PostHog](https://posthog.com/faq) to collect anonymous telemetries to better learn how users use Keep (masked screen recordings for CLI commands)
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

- [Tal](https://github.com/talboren)
- [Shahar Glazner](https://github.com/shahargl)

Want to become a top contributor? Join our Slack and DM Tal, Shahar, or Furkan.

### Contributors
Thank you for contributing and continuously making <b>Keep</b> better, <b>you're awesome</b> 🫶

<a href="https://github.com/keephq/keep/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=keephq/keep" />
</a>
