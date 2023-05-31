---
sidebar_label: HTTP Provider
---

# HTTP Provider

:::note Brief Description
HTTP Provider is a provider used to query/notify using HTTP requests
:::

## Inputs
The `query` method of the `HttpProvider` class takes the following inputs:

- `url`: The URL of the HTTP endpoint to query.
- `method`: The HTTP method to use for the query, either "GET", "POST", "PUT", or "DELETE".
- `headers`: A dictionary of headers to include in the HTTP request.
- `body`: A dictionary of data to include in the HTTP request body, only used for `POST`, `PUT` requests.
- `params`: A dictionary of query parameters to include in the URL of the HTTP request.

## Outputs
The `query` method returns the JSON representation of the HTTP response, if the response is JSON-encoded, otherwise it returns the response text as a string.

## Authentication Parameters
The `HttpProvider` class does not have any authentication parameters, but the authentication for the HTTP endpoint can be included in the headers or in the URL query parameters.

## Connecting with the Provider
To connect to the provider, you can instantiate an instance of the `HttpProvider` class, providing a `provider_id` and a `ProviderConfig` object. Then you can call the `query` method to query the HTTP endpoint.

## Notes
The code logs some debug information about the requests being sent, including the request headers, body, and query parameters. This information should not contain sensitive information, but it's important to make sure of that before using this provider in production.

## Useful Links
- [requests library documentation](https://docs.python-requests.org/en/latest/)
