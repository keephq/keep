<div align="center">
    <img src="/assets/keep.png?raw=true" width="86">
</div>

<h1 align="center">The open-source alerts management and automation platform</h1>
<br />


<div align="center">
    <a href="https://github.com/keephq/keep/blob/main/LICENSE">
        <img src="https://img.shields.io/github/license/keephq/keep" />
    </a>
    <a href="https://slack.keephq.dev">
      <img src="https://img.shields.io/badge/Join-important.svg?color=4A154B&label=Slack&logo=slack&labelColor=334155&logoColor=f5f5f5" alt="Join Slack" />
    </a>
    <a href="https://codecov.io/gh/keephq/keep" >
        <img src="https://codecov.io/gh/keephq/keep/branch/main/graph/badge.svg?token=2VT6XYMRGS"/>
    </a>
</div>
<p align="center">
    <a href="#why-keep">Why Keep?</a>
    ·
    <a href="#getting-started">Getting started</a>
    ·
    <a href="#supported-providers">Supported tools and integrations</a>
    ·
    <a href="https://docs.keephq.dev">Docs</a>
    ·
    <a href="https://platform.keephq.dev">Try it out</a>
    ·
    <a href="https://keephq.dev">Website</a>
    ·
    <a href="https://github.com/keephq/keep/issues/new?assignees=&labels=bug&template=bug_report.md&title=">Report Bug</a>
    ·
    <a href="https://slack.keephq.dev">Slack Community</a>
</p>
<h3 align="center">
Keep makes it easy to consolidate all your alerts into a single pane of glass and to orchestrate workflows to automate your end-to-end processes. <br /><br /> Enrich any tool with <a href="https://docs.datadoghq.com/service_management/workflows/">Datadog Workflow Automation</a> like capabilities.
</h3 >



## How does it work?
1. **Connect your tools**: Connect everything from monitoring platforms to databases and ticketing systems.
<div align="center">

| Connect providers | Receive alerts |
|----------|----------|
| <img src="/assets/connect_providers.gif" />    | <img src="/assets/view_alerts.gif" />   |

</div>

2. **Set up Workflows**: Initiate automated workflows in response to alerts or based on custom intervals.

<div align="center">


| Create and upload workflows |
|----------|
| <img src="/assets/upload_workflow.gif" />    |

</div>

3. **Operational efficiency**: Automate your alert handling to focus your team's efforts on what really matters.


## Why Keep?
1. **Centralized dashboard**: Manage all your alerts across different platforms in a single interface.
2. **Noise reduction**: Deduplicate and correlate alerts to reduce alert fatigue.
3. **Automation**: Trigger workflows for alert enrichment and response.
4. **Developer-first**: Keep is API-first and lets you manage your workflows as code.
5. **Works with every tool**: Plenty of [supported providers](#supported-providers) and more to come.


## Workflows
The easiest way of thinking about Workflow in Keep is GitHub Actions. At its core, a Workflow in Keep is a declarative YAML file, composed of triggers, steps, and actions and serves to manage, enrich, and automate responses to alerts:
```yaml
workflow:
  id: most-basic-keep-workflow
  description: send a slack message when a cloudwatch alarm is triggered
  # workflow triggers - supports alerts, interval, and manual triggers
  triggers:
    - type: alert
      filters:
        - key: source
          value: cloudwatch
    - type: manual
  # list of steps that can add context to your alert
  steps:
    - name: enrich-alert-with-more-data-from-a-database
      provider:
        type: bigquery
        config: "{{ providers.bigquery-prod }}"
        with:
          query: "SELECT customer_id, customer_type as date FROM `customers_prod` LIMIT 1"
  # list of actions that can automate response and do things with your alert
  actions:
    - name: trigger-slack
      provider:
        type: slack
        config: " {{ providers.slack-prod }} "
        with:
          message: "Got alarm from aws cloudwatch! {{ alert.name }}"
```
Workflow triggers can either be executed manually when an alert is activated or run at predefined intervals. More examples can be found [here](https://github.com/keephq/keep/tree/main/examples/workflows).

## Supported Providers
> Missing any? Just submit a [new provider issue](https://github.com/keephq/keep/issues/new?assignees=&labels=provider&projects=&template=new_provider_request.md&title=) and we will add it in the blink of an eye.

<h3 align="center">Observability tools</h3>
<p align="center">
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/newrelic-icon.png?raw=true"/>
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
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/zabbix-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/sentry-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/dynatrace-icon.png?raw=true"/>
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
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/discord-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/twilio-icon.png?raw=true"/>
</p>
<h3 align="center">Incident Management tools</h2>
<p align="center">
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/pagerduty-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/opsgenie-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/zenduty-icon.png?raw=true"/>
</p>
<h3 align="center">Ticketing tools</h2>
<p align="center">
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/jira-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/trello-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/github-icon.png?raw=true"/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <img width=32 height=32 src="https://github.com/keephq/keep/blob/main/keep-ui/public/icons/servicenow-icon.png?raw=true"/>
</p>


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
wget -O docker-compose.yml https://raw.githubusercontent.com/keephq/keep/main/docker-compose.yml
docker-compose -f docker-compose.yml up
```
The UI is now available at http://localhost:3000 and the backend is available at http://localhost:8080.
#### Local development
You can also start Keep within your favorite IDE, e.g. [VSCode](https://docs.keephq.dev/development/getting-started#vscode)



#### Wanna get Keep up and running in production? Go through our detailed [development guide](https://docs.keephq.dev/development)

## 🫵 Keepers

Thank you for contributing and continuously making <b>Keep</b> better, <b>you're awesome</b> 🫶

<a href="https://github.com/keephq/keep/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=keephq/keep" />
</a>
