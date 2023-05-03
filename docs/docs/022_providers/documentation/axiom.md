---
sidebar_label: Axiom Provider
---

# Axiom Provider

:::note Brief Description
Axiom Provider is a class that allows to ingest/digest data from Axiom.
:::

## Inputs

- **query** (required): AQL to execute
- **dataset** (required): Dataset to query
- **organization_id** (optional): Override the given organization id from configuration
- **nocache** (optional): Whether to cache the response or not
- **startTime** (optional): Start time, defaults to UTC now in ISO format.
- **endTime** (optional): End time, defaults to UTC now in ISO format.

## Outputs

Axiom does not currently support the `notify` function.

## Authentication Parameters

The Axiom Provider uses API token authentication. You need to provide the following authentication parameters to connect to Axiom:

- **api_token** (required): Your Axiom API token.
- **organization_id** (optional): The organization ID to access datasets in.

## Connecting with the Provider

To connect to Axiom, you need to create an API token from your Axiom account. Follow these steps:

1. Log in to your Axiom account.
2. Go to the **API Access** page under the **Settings** menu.
3. Click the **Create Token** button and enter a name for the token.
4. Copy the token value and keep it safe.
5. Add the token value to the `authentication` section in the Axiom Provider configuration.

To access datasets, you need to provide the organization ID. You can find your organization ID in the URL of the Axiom web app. For example, if your Axiom URL is `https://app.axiom.co/organizations/1234`, then your organization ID is `1234`.

## Notes

- This provider supports a limited set of features provided by the Axiom API.
- The `startTime` and `endTime` parameters use ISO-8601 format.
- The `query` function returns the response in JSON format from the Axiom API.

## Useful Links

- [Axiom API Documentation](https://axiom.co/docs/restapi/introduction)
