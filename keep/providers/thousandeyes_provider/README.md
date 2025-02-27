# ThousandEyes Setup

This guide provides instructions on setting up the ThousandEyes provider for Keep.

## Prerequisites

* A ThousandEyes account with API access.
* An API token generated from your ThousandEyes account.

## Configuration

To use the ThousandEyes provider with Keep, you need to configure it with your API token.

1.  **Generate API Token:**
    * Log in to your ThousandEyes account.
    * Navigate to "Settings" -> "User Settings".
    * Scroll down to the "API Keys" section.
    * Click "Generate API Key".
    * Copy the generated API token.

2.  **Configure Keep:**
    * Add the following configuration to your Keep setup:

        ```yaml
        providers:
          thousandeyes:
            api_token: "your_thousandeyes_api_token"
        ```

    * Replace `"your_thousandeyes_api_token"` with the API token you generated.

## Testing the Provider

You can test the ThousandEyes provider by using Keep to fetch alerts.

1.  **Use Keep to Fetch Alerts:**
    * Use the Keep CLI or API to execute a workflow that uses the ThousandEyes provider to fetch alerts.

    * Example python code snippet.

        ```python
        from keep.providers.thousandeyes_provider.thousandeyes_provider import ThousandEyesProvider

        # Initialize the provider
        provider = ThousandEyesProvider(context_manager, provider_id="thousandeyes", config={"authentication": {"api_token": "your_api_token"}})

        # Fetch alerts
        alerts = provider.get_alerts()
        print(alerts)
        ```

    * Replace `your_api_token` with your ThousandEyes API token.

## Troubleshooting

* **Invalid API Token:**
    * Ensure the API token is correct and has the necessary permissions to access the ThousandEyes API.
* **API Rate Limits:**
    * If you encounter rate-limiting errors, check the ThousandEyes API rate limits and adjust your usage accordingly.
* **Network Issues:**
    * Verify that Keep has network connectivity to the ThousandEyes API endpoints.