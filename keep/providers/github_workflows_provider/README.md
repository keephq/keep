# GitHub Workflows Provider

## Overview

The **GitHub Workflows** provider monitors GitHub Actions workflow runs and surfaces failures (and other non-success conclusions) as alerts in Keep.

It supports **two modes**:

| Mode | How it works |
|------|-------------|
| **Pull (polling)** | Keep periodically calls the GitHub Actions API to fetch recent completed workflow runs and raises alerts for non-success conclusions |
| **Push (webhook)** | GitHub sends `workflow_run` webhook events to Keep, and the provider converts them into alerts |

## Authentication

| Parameter | Required | Description |
|-----------|----------|-------------|
| `personal_access_token` | Yes | GitHub Personal Access Token (classic or fine-grained) with `actions:read` scope |
| `repositories` | Yes | Comma-separated list of repositories to monitor (e.g. `owner/repo1, owner/repo2`) |
| `api_url` | No | GitHub API base URL. Defaults to `https://api.github.com`. Set to `https://your-ghes.example.com/api/v3` for GitHub Enterprise Server |

### Creating a PAT

1. Go to **Settings → Developer Settings → Personal Access Tokens → Fine-grained tokens**
2. Click **Generate new token**
3. Under **Repository access**, select the repositories you want to monitor
4. Under **Permissions → Repository permissions**, grant **Actions: Read-only**
5. Click **Generate token** and copy it

## Alert Mapping

### Severity

| Workflow Conclusion | Alert Severity |
|--------------------|---------------|
| `failure` | Critical |
| `startup_failure` | Critical |
| `timed_out` | High |
| `cancelled` | Warning |
| `action_required` | Info |
| `success` | Info |

### Status

| Workflow Conclusion | Alert Status |
|--------------------|-------------|
| `failure`, `cancelled`, `timed_out`, `startup_failure` | Firing |
| `action_required` | Pending |
| `success` | Resolved |

## Webhook Setup

To receive real-time alerts via webhooks:

1. Go to your repository's **Settings → Webhooks → Add webhook**
2. Set the **Payload URL** to your Keep webhook endpoint: `https://your-keep-instance/alerts/event/github_workflows`
3. Set **Content type** to `application/json`
4. Under **Which events would you like to trigger this webhook?**, select **Let me select individual events**
5. Check **Workflow runs**
6. Click **Add webhook**

## Notify (Workflow Dispatch)

The provider also supports triggering workflows via the `_notify()` method:

```python
# Dispatch a workflow
provider.notify(
    workflow_id="build.yml",
    ref="main",
    inputs={"deploy_env": "staging"}
)
```

## Fingerprinting

Alerts use the following fingerprint format:
```
github-workflow-{owner/repo}-{run_id}
```

This ensures each workflow run produces a unique, trackable alert.

## Example Alert Labels

Each alert includes rich metadata in `labels`:

| Label | Example |
|-------|---------|
| `repo` | `keephq/keep` |
| `workflow` | `CI` |
| `run_number` | `42` |
| `branch` | `main` |
| `event` | `push` |
| `actor` | `dev-user` |
| `conclusion` | `failure` |
| `commit_message` | `fix: resolve auth bug` |

## Useful Links

- [GitHub Actions API](https://docs.github.com/en/rest/actions/workflow-runs)
- [Webhook events: workflow_run](https://docs.github.com/en/webhooks/webhook-events-and-payloads#workflow_run)
- [Creating a PAT](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
