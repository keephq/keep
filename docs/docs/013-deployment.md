---
sidebar_label: Deployment
sidebar_position: 3
---

# Deployment

After writing some alerts with Keep, you may now want to use Keep in production! For that, you can easily deploy Keep on an environment other than your local station.

Keep currently supports [Docker](#docker) and [Render](#render).
:::warning Missing something?
 Want to deploy Keep on a specific platform that is not yet supported? [Just open an issue](https://github.com/keephq/keep/issues/new?assignees=&labels=&template=feature_request.md&title=feature:%20new%20deployment%20option) and we will get to it ASAP!
:::

## E2E

Run *Keep* full stack (Console & API)
```bash
docker-compose up
```
Or
```bash
docker-compose -f docker-compose.dev.yml up --build
```
If you want to run Keep in [development mode](https://development-mode-url)

:::note OpenAI Integration
Please note that some features used by Keep requires OpenAI API key to work.
Export `OPENAI_API_KEY=sk-YOUR_API_KEY` before running docker-compose to make them available.

For example:
```bash
OPENAI_API_KEY=sk-YOUR_API_KEY docker-compose up
```
:::

### Docker

## CLI

Run *Keep* alerting engine (The CLI)

### Docker

Configure the Slack provider (See "[Run locally](https://github.com/keephq/keep#get-a-slack-incoming-webhook-using-this-tutorial-and-use-keep-to-configure-it)" on how to obtain the webhook URL)

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

\* Refer to [Run locally](https://github.com/keephq/keep#get-a-slack-incoming-webhook-using-this-tutorial-and-use-keep-to-configure-it) on how to obtain the webhook URL
