# Apache SkyWalking Provider

Apache SkyWalking is an open-source observability platform used to collect, analyze, aggregate and visualize data from services and cloud native infrastructures.

## Authentication Configuration

To connect Keep to SkyWalking, you need the GraphQL endpoint of your SkyWalking OAP (Observability Analysis Platform) server.

*   **URL**: The full URL to the SkyWalking GraphQL endpoint (e.g., `http://skywalking-oap:12800/graphql`).
*   **Username** (Optional): If your SkyWalking UI/OAP is protected by basic authentication.
*   **Password** (Optional): If your SkyWalking UI/OAP is protected by basic authentication.

## Scopes

*   **connectivity**: Tests if Keep can connect to the SkyWalking OAP server and execute a basic GraphQL query.

## Webhook Configuration

Keep can also receive alerts from SkyWalking via its HTTP webhook alarm setting.

1.  In your SkyWalking `alarm-settings.yml`, add a webhook receiver:
    ```yaml
    webhooks:
      - http://{KEEP_WEBHOOK_API_URL}
    ```
2.  SkyWalking will then push alarms to Keep as they occur.

## Querying

You can use the SkyWalking provider to execute custom GraphQL queries. For example:

```yaml
# Get all available layers
query: \"{ listLayers }\"
```
