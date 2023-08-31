<div align="center">
    <img src="/assets/keep.png?raw=true" width="86">
</div>

<h1 align="center">The open-source alerts management and automation platform</h1>
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
<p align="center">
    <a href="https://platform.keephq.dev">Try it out</a>
    ·
    <a href="https://docs.keephq.dev/overview/examples">Examples</a>
    ·
    <a href="https://docs.keephq.dev/providers/overview">Providers</a>
    ·
    <a href="https://docs.keephq.dev">Docs</a>
    ·
    <a href="https://keephq.dev">Website</a>
    ·
    <a href="https://github.com/keephq/keep/issues/new?assignees=&labels=bug&template=bug_report.md&title=">Report Bug</a>
    ·
    <a href="https://keephq.dev/slack">Slack Community</a>
</p>
<h3 align="center">
Keep makes it easy to consolidate all your alerts into a single pane of glass and to orchestrate workflows to automate your end-to-end processes. <br /><br /> Like Datadog Workflow Automation but for any tool.
</h3 >


### How does it work?

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


### Why Keep?
1. **Centralized dashboard**: Manage all your alerts across different platforms in a single interface.
2. **Noise reduction**: Deduplicate and correlate alerts to reduce alert fatigue.
3. **Automation**: Trigger workflows for alert enrichment and response.
4. **Developer-first**: Keep is API-first and let you manage your workflows as code.



### For developers
#### Overview
Keep composed of three main components:
1. [Keep UI](https://github.com/keephq/keep/tree/main/keep-ui) - A NextJS app to connect your providers, centralize alerts and create the workflows.
2. [Keep Backend](https://github.com/keephq/keep/tree/main/keep) - A FastAPI server that implements the buisness logic behind Keep, including integrating with the tools, working with alerts and scheduling and running the workflows.
3. [Keep CLI](https://github.com/keephq/keep/blob/main/keep/cli/cli.py) - A CLI that let you control and manage Keep via CLI.

>**Disclaimer**: we use [PostHog](https://posthog.com/faq) to collect anonymous telemetries to better learn how users use Keep (masked screen recordings for and CLI commands)
To turn PostHog off, set the `DISABLE_POSTHOG` environment variable.

#### Quickstart
##### Spinning up Keep with docker-compose
The easiest way to start with Keep is to run it via docker-compose:
```shell
wget -O docker-compose.yml https://raw.githubusercontent.com/keephq/keep/main/docker-compose.yml
docker-compose -f docker-compose.yml up
```
The UI is now available at http://localhost:3000 and the backend is available at http://localhost:8080.
##### Local development
You can also start Keep within your favourite IDE, e.g. [VSCode](https://docs.keephq.dev/development/getting-started#vscode)



##### Wanna have your alerts up and running in production? Go through our more detailed [Deployment Guide](https://keephq.wiki/deployment)

## 🔍 Learn more

- Share feedback/ask questions via our [Slack](https://keephq.dev/slack)
- Explore [the full list of supported providers](https://github.com/keephq/keep/tree/main/keep/providers)
- Explore the [documentation](https://docs.keephq.dev)
- [Adding a new provider](https://docs.keephq.dev/development/adding-a-new-provider)
- Check out our [website](https://www.keephq.dev)

## 🫵 Keepers

Thank you for contributing and continuously making <b>Keep</b> better, <b>you're awesome</b> 🫶

<a href="https://github.com/keephq/keep/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=keephq/keep" />
</a>
