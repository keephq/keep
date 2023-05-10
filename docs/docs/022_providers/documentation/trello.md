---
sidebar_label: Trello Provider
---

# Trello

:::note Brief Description
Trello provider is a provider used to query data from Trello
:::

## Inputs
The `query` function take following parameters as inputs:
- `board_id`: Required. Trello board id
- `filter`: Optional. Comma seperated list of trello events that want to query, default value is 'createCard' 


## Outputs


## Authentication Parameters
The `query` function requires an `api_key` and `api_token` from Trello, which can obtained by making custom power-up in Trello admin.

## Connecting with the Provider
1. Go to https://trello.com/power-ups/admin to create custom power-up.
2. Create new power-up and add basic details like name, email address, etc.
3. Once it is created, navigate inside power-up and go to API Key section.
4. There click on `Generate a new API key` and it will generate API Key, that will be used as `api_key`.
5. For generating `api_token`, there is option to generate Token manually, click on that and authorize the application.

## Notes


## Useful Links
- https://developer.atlassian.com/cloud/trello/guides/power-ups/your-first-power-up/
- https://trello.com/power-ups/admin
