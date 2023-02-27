---
sidebar_label: Teams Provider
---

# Teams Provider

:::note Brief Description
Teams Provider is a provider that allows to notify alerts to Microsoft Teams chats.
:::

## Inputs
The `notify` function in the `TeamsProvider` class takes the following parameters:
```python
kwargs (dict):
    message (str): The message to send. *Required*
    typeCard (str): The card type. (MessageCard is default)
    themeColor (str): Hexadecimal color.
    sections (array): Array of custom informations
```

## Outputs
*No information yet, feel free to contribute it using the "Edit this page" link the bottom of the page*

## Authentication Parameters
The TeamsProviderAuthConfig class takes the following parameters:

- `webhook_url` (str): associated with the channel requires to trigger the message to the respective channel. *Required*

## Connecting with the Provider
1 - Open the Microsoft Teams application or website and select the team or channel where you want to add the webhook.

2 - Click on the three-dot icon next to the team or channel name and select "Connectors" from the dropdown menu.

3 - Search for "Incoming Webhook" and click on the "Add" button.

3 - Give your webhook a name and an optional icon, then click on the "Create" button.

3 - Copy the webhook URL that is generated and save it for later use.

4 - Select the options that you want to configure for your webhook, such as the default name and avatar that will be used when posting messages.

5 - Click on the "Save" button to save your webhook settings.

You can now use the webhook URL to send messages to the selected channel or team in Microsoft Teams.

## Notes
*No information yet, feel free to contribute it using the "Edit this page" link the bottom of the page*


## Useful Links
- https://learn.microsoft.com/pt-br/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook
