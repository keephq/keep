<div align="center">
    <img src="/docs/static/img/keep.png?raw=true" width="86">
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
Simple alerting tool, builtin providers (e.g. sentry/datadog or slack/pagerduty), 100% open sourced, free forever.
</h4>
<div align="center">

- Simple and intuitive (GitHub actions-like) syntax.
- Declarative alerting that can be easily managed and versioned in your version control and service repository.
- Alerts from multiple data sources for added context and insights.
- Freedom from vendor lock-in, making it easier to switch to a different observability tool if and when needed.

</div>

<p align="center">
    <br />
    <a href="https://keephq.wiki/" rel="dofollow"><strong>Get started »</strong></a>
    <br />
    <br />
    <a href="https://github.com/orgs/keephq/projects/1">Roadmap</a>
    ·
    <a href="https://github.com/keephq/keep/tree/main/examples">Examples</a>
    ·
    <a href="https://github.com/keephq/keep/tree/main/keep/providers">Providers</a>
    ·
    <a href="https://keephq.wiki/">Docs</a>
    ·
    <a href="https://keephq.dev">Website</a>
    ·
    <a href="https://keephq.wiki/providers/new-provider">Add Providers</a>
    ·
    <a href="https://github.com/keephq/keep/issues/new?assignees=&labels=bug&template=bug_report.md&title=">Report Bug</a>
    ·
    <a href="https://keephq.dev/slack">Slack Community</a>
</p>

## 🗼 A glance of Keep

Keep is a simple CLI tool that contains everything you need to start creating Alerts.

- 10s of providers ready to use with your own data
- Simple CLI tool to configure, trigger and test your alerts
- Easily deployable via docker, vercel, github actions, etc.
- Alerts are managed by simple yaml files that are human-readable

Brought to you by developers, EASY to use and managable by code.

## 🚨 Providers

[Providers](https://keephq.wiki/providers/what-is-a-provider) are Keep's way of interacting with 3rd party products; Keep uses them either to query data or to send notifications.

We tried our best to cover all common providers, [missing any?](https://github.com/keephq/keep/issues/new?assignees=&labels=feature,provider&template=feature_request.md&title=Missing%20PROVIDER_NAME), providers include:

- **Cloud**: AWS, GCP, Azure, etc.
- **Monitoring**: Sentry, New Relic, Datadog, etc.
- **Incident Management**: PagerDuty, OpsGenie, etc.
- **Communication**: Email, Slack, Console, etc.
- [and more...](https://github.com/keephq/keep/tree/main/keep/providers)

## 🚀 Quickstart

### Run locally

Try our first mock alert and get it up and running in <5 minutes - Ready? Let's Go! ⏰

<h5>First, clone Keep repository:</h5>

```shell
git clone https://github.com/keephq/keep.git && cd keep
```

<h5>Install Keep CLI</h5>

```shell
pip install .
```

or

```shell
poetry shell
poetry install
```

<h5>From now on, Keep should be installed locally and accessible from your CLI, test it by executing:</h5>


```
keep version
```

Get a Slack incoming webhook using [this tutorial](https://api.slack.com/messaging/webhooks) and use Keep to configure it:

```
keep config provider --provider-type slack --provider-id slack-demo
```


Paste the Slack Incoming Webhook URL (e.g. <https://hooks.slack.com/services/...>) and you're good to go 👌

<h6>**If you don't want to create your own webhook, you can follow these easy 3 steps:**

1. Go to [keep's slack](https://keephq.dev/slack).

2. Enter the # alerts-playground channel.

3. In the channel's topic, you can find the webhook provided by Keep.

<h5>Let's now execute our example "Paper DB has insufficient disk space" alert</h5>

```bash
keep run --alerts-file examples/alerts/db_disk_space.yml
```

<div align="center">
    Voilà 🥳
    <br />
    <img src="/docs/static/img/alert-example.png">
    <br />
    You should have received your first "Dunder Mifflin Paper Company" alert in Slack by now.
    <br />
</div>


### Docker

Configure the Slack provider (See "[Run locally](https://github.com/keephq/keep#from-now-on-keep-should-be-installed-locally-and-accessible-from-your-cli-test-it-by-executing)" on how to obtain the webhook URL)

```bash
docker run -v ${PWD}:/app -it keephq/cli config provider --provider-type slack --provider-id slack-demo
```

You should now have a providers.yaml file created locally

Run Keep and execute our example "Paper DB has insufficient disk space" alert

```bash
docker run -v ${PWD}:/app -it keephq/cli -j run --alert-url https://raw.githubusercontent.com/keephq/keep/main/examples/alerts/db_disk_space.yml
```

### Render
Click the Deploy to Render button to deploy Keep as a background worker running in [Render](https://www.render.com)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/keephq/keep)

To run Keep and execute our example "Paper DB has insufficient disk space" alert, you will need to configure you Slack provider.
<br />
When clicking the Deploy to Render button, you will be asked to provide the `KEEP_PROVIDER_SLACK_DEMO` environment variable, this is the expected format:

```json
{"authentication": {"webhook_url": "https://hooks.slack.com/services/..."}}
```

\* Refer to [Run locally](https://github.com/keephq/keep#from-now-on-keep-should-be-installed-locally-and-accessible-from-your-cli-test-it-by-executing) on how to obtain the webhook URL

##### Wanna have your alerts up and running in production? Go through our more detailed [Deployment Guide](https://keephq.wiki/deployment)

## 🔍 Learn more

- Share feedback/ask questions via our [Slack](https://keephq.dev/slack)
- Explore [the full list of supported providers](https://github.com/keephq/keep/tree/main/keep/providers)
- Explore the [documentation](https://keephq.wiki)
- [Adding a new provider](https://keephq.wiki/providers/new-provider)
- Check out our [website](https://www.keephq.dev)

## 🫵 Keepers

Thank you for contributing and continuously making <b>Keep</b> better, <b>you're awesome</b> 🫶

<a href="https://github.com/keephq/keep/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=keephq/keep" />
</a>
