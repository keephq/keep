---
sidebar_label: Deployment
sidebar_position: 3
---

# Deployment

## Docker

Configure the Slack provider (See "[Run locally](https://github.com/keephq/keep#from-now-on-keep-should-be-installed-locally-and-accessible-from-your-cli-test-it-by-executing)" on how to obtain the webhook URL)

```bash
docker run -v ${PWD}:/app -it keephq/cli config provider --provider-type slack --provider-id slack-demo
```

You should now have a providers.yaml file created locally

Run Keep and execute our example "Paper DB has insufficient disk space" alert

```bash
docker run -v ${PWD}:/app -it keephq/cli -j run --alert-url https://raw.githubusercontent.com/keephq/keep/main/examples/alerts/db_disk_space.yml
```

## Render
Click the Deploy to Render button to deploy Keep as a background worker running in [Render](https://www.render.com)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

To run Keep and execute our example "Paper DB has insufficient disk space" alert, you will need to configure you Slack provider.
<br />
When clicking the Deploy to Render button, you will be asked to provide the `KEEP_PROVIDER_SLACK_DEMO` environment variable, this is the expected format:

```json
{"authentication": {"webhook_url": "https://hooks.slack.com/services/..."}}
```

\* Refer to [Run locally](https://github.com/keephq/keep#from-now-on-keep-should-be-installed-locally-and-accessible-from-your-cli-test-it-by-executing) on how to obtain the webhook URL

#### Want to deploy Keep on a specific platform? [Just open an issue](https://github.com/keephq/keep/issues/new?assignees=&labels=&template=feature_request.md&title=feature:%20new%20deployment%20option) and we will get to it ASAP!
