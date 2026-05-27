# Zenduty Provider

Zenduty is an incident management platform that helps teams manage their incident response lifecycle.

## Authentication

1. Log in to your Zenduty account.
2. Go to **Account Settings** -> **Account Token**.
3. Copy your **Account Token** (this is your `api_key`).
4. (Optional) For the Events API, go to a **Service** -> **Integrations**, add a "Zenduty" integration, and copy the **Integration Key**.

## Configuration

- `api_key`: Your Zenduty Account Token.
- `integration_key` (Optional): Key for triggering alerts via the Events API.
