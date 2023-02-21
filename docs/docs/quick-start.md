---
sidebar_label: Quick Start
sidebar_position: 2
---

# 🚀 Quickstart

## Run locally
Try our first mock alert and get it up and running in <5 minutes - Ready? Let's Go! ⏰

### Clone and install

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
poetry install
```

<h5>From now on, Keep should be installed locally and accessible from your CLI, test it by executing:</h5>

```
keep version
```

<h5>Get a Slack Incoming Webhook using [this tutorial](https://api.slack.com/messaging/webhooks) and use use Keep to configure it</h5>

```
keep config provider --provider-type slack --provider-id slack-demo
```
Paste the Slack Incoming Webhook URL (e.g. https://hooks.slack.com/services/...) and you're good to go 👌

<h5>Let's now execute our example "Paper DB has insufficient disk space" alert</h5>

```bash
keep run --alerts-file examples/alerts/db_disk_space.yml
```

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

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

To run Keep and execute our example "Paper DB has insufficient disk space" alert, you will need to configure you Slack provider.
<br />
When clicking the Deploy to Render button, you will be asked to provide the `KEEP_PROVIDER_SLACK_DEMO` environment variable, this is the expected format:

```json
{"authentication": {"webhook_url": "https://hooks.slack.com/services/..."}}
```

\* Refer to [Run locally](https://github.com/keephq/keep#from-now-on-keep-should-be-installed-locally-and-accessible-from-your-cli-test-it-by-executing) on how to obtain the webhook URL

<h5>Congrats 🥳 You should have received your first "Dunder Mifflin Paper Company" alert in Slack by now.</h5>

Wanna have your alerts up and running in production? Go through our more detailed [Getting Started Guide](https://keephq.wiki/getting-started).

## Auto Completion

<h4>Keep's CLI supports shell auto-completion, which can make your life a lot more easier 😌</h4>

If you're using zsh, add this to `~/.zshrc`
```shell
eval "$(_KEEP_COMPLETE=zsh_source keep)"
```


If you're using bash, add this to `~/.bashrc`
```bash
eval "$(_KEEP_COMPLETE=bash_source keep)"
```


> Using eval means that the command is invoked and evaluated every time a shell is started, which can delay shell responsiveness. To speed it up, write the generated script to a file, then source that.
