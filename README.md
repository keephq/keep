<div align="center">

<img src="/assets/keep.png?raw=true">

</div>

<h1 align="center">Alerting. By developers, for developers.</h1>
<br />
<div align="center">
    <a href="https://github.com/keephq/keep/blob/main/LICENSE">
        <img src="https://img.shields.io/github/license/keephq/keep" />
    </a>
    <a href="https://keephq.dev/slack">
        <img src="https://img.shields.io/badge/Chat-on%20Slack-blueviolet" alt="Slack community channel" />
    </a>
</div>

<h4 align="center">
Simple Alerting tool, Builtin providers (e.g. sentry/datadog or slack/pagerduty), 100% open sourced, free forever.
</h4>

<h4 align="center">
Manage your alerts by code, write better more actionable and accurate alerts with Keep scoring system (coming soon).
</h4>

<p align="center">
    <br />
    <a href="https://keephq.wiki/" rel="dofollow"><strong>Get started »</strong></a>
    <br />
    <br />
    <a href="https://github.com/keephq/keep/tree/main/keep/providers">Providers</a>
    ·
    <a href="https://keephq.wiki/">Docs</a>
    ·
    <a href="https://keephq.dev">Website</a>
    ·
    <a href="https://keephq.wiki/new-provider">Add New Provider</a>
    ·
    <a href="https://github.com/keephq/keep/issues">Report Bug</a>
    ·
    <a href="https://getkeep.dev/slack">Slack Community</a>
</p>

## 🗼 Keep at a glance

Keep is a simple CLI tool that contains everything you need to start creating your alerts.

-   10s of providers ready to use with your own data
-   simple CLI tool to configure, trigger and test your alerts
-   easyily deployable via docker, vercel, github actions, etc.

## 🚀 Quickstart

### Run locally
Try your first (mock) alert up and get it running in <5 minutes - Ready? Let's Go! ⏰

First, clone and install Keep:

```shell
git clone https://github.com/keephq/keep.git && cd keep
```

```shell
pip install .
```
or
```shell
poetry install
```

From now on, Keep should be installed locally and accessible from your CLI. Test it with running:

```
keep version
```

Next, get a Slack Incoming Webhook using [this tutorial](https://api.slack.com/messaging/webhooks) and use use Keep to configure it

```
keep config provider --provider-type slack --provider-id slack-demo
```

And paste the Slack Incoming Webhook URL (e.g. https://hooks.slack.com/services/XXXX/XXXXXXXX/XXXXXXXXXXXX)

Let's now execute our example "Paper DB has insufficient disk space" alert

```bash
keep run --alerts-file examples/alerts/db_disk_space.yml
```

Congrats 🥳 You should have received your first "Dunder Mifflin Paper Company" alert in Slack by now.

Wanna have your alerts up and running in production? Go through our more detailed [Getting Started Guide](https://keephq.wiki/getting-started).
