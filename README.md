<div align="center">
    <img src="/assets/keep.png?raw=true" width="86">
</div>

<h1 align="center">The open-source alerts management platform</h1>
<br />

<div align="center">
    <a href="https://github.com/keephq/keep/blob/main/LICENSE">
        <img src="https://img.shields.io/github/license/keephq/keep" />
    </a>
    <a href="https://keephq.dev/slack">
        <img src="https://img.shields.io/badge/Chat-on%20Slack-blueviolet" alt="Slack community channel" />
    </a>
    <a href="https://codecov.io/gh/keephq/keep" >
        <img src="https://codecov.io/gh/keephq/keep/branch/main/graph/badge.svg?token=2VT6XYMRGS"/>
    </a>
</div>

<h4 align="center">
Keep enables you to create, manage, test, and maintain your alerts all in one place.
</h4>
<div align="center">

- *Integrations*: Integrates with your existing tools (e.g. grafana/sentry/datadog/slack/pagerduty)
- *Intutive*: Create alerts via a simple and intuitive (GitHub actions-like) syntax.
- *Alerts as code*: Declarative alerting that can be easily managed and versioned in your version control and service repository.
- *Alerts as workflows*: Create alerts from multiple data sources for added context and insights.

</div>

<p align="center">
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
    <a href="https://www.keephq.wiki/platform/core/providers/new-provider">Add Providers</a>
    ·
    <a href="https://github.com/keephq/keep/issues/new?assignees=&labels=bug&template=bug_report.md&title=">Report Bug</a>
    ·
    <a href="https://keephq.dev/slack">Slack Community</a>
</p>

#### 🚀 Quickstart
Keep has two main component that play with each other:
1. [Keep UI](https://www.keephq.wiki/platform/ui/getting-started) - UI to manage your alerts, connect providers and install apps.
2. [Keep Core](https://www.keephq.wiki/platform/getting-started) - The engine behind Keep.
#### Keep UI
The easiest way to start with Keep is to run it via docker-compose:
```shell
wget -O docker-compose.yml https://github.com/keephq/keep/blob/main/docker-compose.yml
docker-compose -f docker-compose.yml up
```
Keep UI is now available at http://localhost:3000

#### Keep Core
Try our first mock alert and get it up and running in <5 minutes - Ready? Let's Go! ⏰

First, clone Keep repository:

```shell
git clone https://github.com/keephq/keep.git && cd keep
```

Install Keep CLI

```shell
pip install .
```

or

```shell
poetry shell
poetry install
```

From now on, Keep should be installed locally and accessible from your CLI, test it by executing:


```
keep version
```

<h5>Get a Slack incoming webhook using <a href="https://api.slack.com/messaging/webhooks">this tutorial</a> and use Keep to configure it:</h5>

```
keep config provider --provider-type slack --provider-id slack-demo
```

Paste the Slack Incoming Webhook URL (e.g. <https://hooks.slack.com/services/...>) and you're good to go 👌

<h6>** If you don't want to create your own webhook, you can follow these easy 3 steps: **

1. Go to [keep's slack](https://keephq.dev/slack).

2. Enter the #alerts-playground channel.

3. In the channel's topic, you can find the webhook provided by Keep.

<h5>Let's now execute our example "Paper DB has insufficient disk space" alert</h5>

```bash
keep run --alerts-file examples/alerts/db_disk_space.yml
```

<div align="center">
    Voilà 🥳
    <br />
    <img src="/assets/alert-example.png">
    <br />
    You should have received your first "Dunder Mifflin Paper Company" alert in Slack by now.
    <br />
</div>


##### Docker

Configure the Slack provider (See "[Run locally](https://github.com/keephq/keep#from-now-on-keep-should-be-installed-locally-and-accessible-from-your-cli-test-it-by-executing)" on how to obtain the webhook URL)

```bash
docker run -v ${PWD}:/app -it keephq/cli config provider --provider-type slack --provider-id slack-demo
```

You should now have a providers.yaml file created locally

Run Keep and execute our example "Paper DB has insufficient disk space" alert

```bash
docker run -v ${PWD}:/app -it keephq/cli -j run --alert-url https://raw.githubusercontent.com/keephq/keep/main/examples/alerts/db_disk_space.yml
```

##### Render
Click the Deploy to Render button to deploy Keep as a background worker running in [Render](https://www.render.com)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/keephq/keep)

To run Keep and execute our example "Paper DB has insufficient disk space" alert, you will need to configure you Slack provider.
<br />
When clicking the Deploy to Render button, you will be asked to provide the `KEEP_PROVIDER_SLACK_DEMO` environment variable, this is the expected format:

```json
{"authentication": {"webhook_url": "https://hooks.slack.com/services/..."}}
```

\* Refer to [Run locally](https://github.com/keephq/keep/tree/feature/api-multi-tenant#get-a-slack-incoming-webhook-using-this-tutorial-and-use-keep-to-configure-it) on how to obtain the webhook URL

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
