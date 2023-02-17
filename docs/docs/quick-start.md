---
sidebar_label: Quick Start
sidebar_position: 2
---

# 🚀 Quickstart

## Run locally
Try our first mock alert and get it up and running in <5 minutes - Ready? Let's Go! ⏰

### Docker
Configure:
```
docker run -v ${PWD}:/app -it keep config provider --provider-type slack --provider-id slack-demo
```
Run:
```
docker run -v ${PWD}:/app -it keephq/cli -j run --alerts-file  examples/alerts/db_disk_space.yml
```
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
