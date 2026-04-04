# GitHub Integration for Keep

This integration allows Keep to receive and process alerts from GitHub via webhooks. It supports multiple GitHub event types and automatically converts them into Keep alerts with appropriate statuses and severities.

## Features

- Real-time alert processing via GitHub webhooks
- Support for multiple event types:
  - Issues (opened, closed, reopened)
  - Pull Requests (opened, closed, merged)
  - Push events
  - Workflow runs (success, failure, in progress)
  - Repository vulnerability alerts
  - Security advisories
  - Dependabot alerts
- Automatic signature verification for security
- Configurable alert severity based on event properties
- Comprehensive alert context preservation

## Setup Instructions

### 1. Configure Keep Environment

Add the following environment variables to your Keep deployment:

```bash
# Required: Secret for verifying GitHub webhook signatures
GITHUB_WEBHOOK_SECRET=your_super_secret_key

# Optional: Tenant ID for GitHub alerts (defaults to "default")
KEEP_GITHUB_DEFAULT_TENANT_ID=your_tenant_id
```

### 2. Configure GitHub Webhook

1. Navigate to your GitHub repository or organization settings
2. Go to "Webhooks & Services" (for repositories) or "Webhooks" (for organizations)
3. Click "Add webhook"
4. Set the following values:
   - **Payload URL**: `https://your-keep-instance.com/alerts/github`
   - **Content type**: `application/json`
   - **Secret**: The same value as `GITHUB_WEBHOOK_SECRET` above
   - **Events**: Select the events you want to trigger alerts:
     - Issues
     - Pull requests
     - Pushes
     - Workflow runs
     - Repository vulnerability alerts
     - Security advisories
     - Dependabot alerts
5. Click "Add webhook"

### 3. Verify Integration

After setup, GitHub will send a ping event to verify the webhook. You can check your Keep logs to confirm successful receipt.

## Supported Events

### Issues
- **Opened/Reopened**: Creates a WARNING alert
- **Closed**: Creates a RESOLVED alert
- Custom severity can be set via issue labels (critical, high, moderate, low)

### Pull Requests
- **Opened/Reopened**: Creates an INFO alert
- **Closed/Merged**: Creates a RESOLVED alert

### Push Events
- Creates an INFO alert showing branch and commit information

### Workflow Runs
- **Failure**: Creates an ERROR alert
- **Success**: Creates a RESOLVED alert
- **In Progress/Queued**: Creates a PENDING alert

### Repository Vulnerability Alerts
- **Created**: Creates an alert with severity matching the vulnerability
- **Resolved**: Creates a RESOLVED alert

### Security Advisories
- **Published**: Creates a CRITICAL alert
- **Withdrawn**: Creates a RESOLVED alert

### Dependabot Alerts
- **Open**: Creates an alert with severity matching the vulnerability
- **Fixed/Dismissed**: Creates a RESOLVED alert

## Troubleshooting

### Webhook Not Working
1. Check that `GITHUB_WEBHOOK_SECRET` is correctly set in Keep
2. Verify the webhook URL is accessible from the internet
3. Check GitHub's webhook delivery logs for errors
4. Review Keep's logs for processing errors

### Missing Alerts
1. Ensure the correct events are selected in GitHub webhook settings
2. Check that the webhook is active
3. Verify Keep has the proper tenant permissions

### Authentication Issues
1. Confirm the webhook secret matches between GitHub and Keep
2. Check that HTTPS is used for the webhook URL
3. Ensure there are no firewall restrictions blocking GitHub IPs

## Security Considerations

- Always use a strong, random secret for webhook verification
- Ensure your Keep instance is only accessible over HTTPS
- Regularly rotate your webhook secrets
- Monitor webhook delivery logs for unauthorized attempts

## Customization

To customize alert behavior:
1. Modify the `_github_event_to_alert` function in `github.py`
2. Adjust severity mappings based on your organization's policies
3. Add support for additional GitHub event types by extending the match statement

For advanced customization requiring per-repository or per-organization handling, you can modify the `DEFAULT_GITHUB_TENANT_ID` resolution logic.

## Testing

Run the integration tests with:

```bash
pytest tests/api/alerts/integrations/test_github_integration.py
```

For manual testing during development:
1. Use ngrok to expose your local Keep instance: `ngrok http 8080`
2. Update the GitHub webhook URL to use the ngrok address
3. Trigger events in your GitHub repository to test alert creation