---
sidebar_label: Jira Provider
---

# Jira

:::note Brief Description
Jira provider is a provider used to query data from Jira
:::

## Inputs
The `query` function take following parameters as inputs:
- `host`: Required. Jira host name of the project
- `board_id`: Required. Jira board id
- `email`: Required. Your accout email


## Outputs


## Authentication Parameters
The `query` function requires an `api_token` from Jira.

## Connecting with the Provider
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens to Create API token and generated token should be passed to jira authentication.
2. Get `host` and `board_id` from your respective board from its URL.
3. `email` would be same as of your account email.

## Notes


## Useful Links
- https://id.atlassian.com/manage-profile/security/api-tokens
- https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/#api-rest-agile-1-0-board-boardid-issue-get
