# MongoDB Atlas Provider

The MongoDB Atlas Provider allows Keep to receive and query alerts from [MongoDB Atlas](https://www.mongodb.com/atlas).

## Features

- **Pull alerts** from MongoDB Atlas via the Atlas Admin API (all open alerts for your project)
- **Receive webhook alerts** — configure Atlas to POST alert notifications to Keep's webhook endpoint

## Authentication

You will need a **Programmatic API Key** from MongoDB Atlas with at least **Project Data Access Read Only** scope to pull alerts.
For webhook setup, the key must have **Project Owner** permissions.

1. Go to **Atlas** → **Access Manager** → **API Keys**
2. Create a new key with the appropriate permissions
3. Add your Keep server IP to the API Access List

## Configuration

| Field        | Description                                                                 |
|--------------|-----------------------------------------------------------------------------|
| `public_key` | MongoDB Atlas Programmatic API public key                                   |
| `private_key`| MongoDB Atlas Programmatic API private key (sensitive)                      |
| `group_id`   | MongoDB Atlas Project ID (visible in the URL of your Atlas project console) |

## Setting up Webhooks

1. Go to **MongoDB Atlas** → **Project Settings** → **Integrations** → **Webhook Settings** (or via Alert settings)
2. Add a new Webhook URL pointing to your Keep instance:
   ```
   https://<your-keep-url>/alerts/event/mongoatlas
   ```
3. Once saved, Atlas will POST alert payloads to Keep whenever an alert triggers, resolves, or updates.

## Alert Fields Mapping

| Atlas Field         | Keep Field          |
|---------------------|---------------------|
| `id`                | `id`                |
| `eventTypeName`     | `name`              |
| `status`            | `status`            |
| `typeName`          | `severity`          |
| `created`           | `createdAt`         |
| `updated`           | `lastReceived`      |
| `resolved`          | `resolvedAt`        |
| `clusterName`       | `cluster_name`      |
| `hostnameAndPort`   | `host`              |
| `metricName`        | `metric_name`       |
| `currentValue`      | `description`       |

## References

- [MongoDB Atlas Alerts Documentation](https://www.mongodb.com/docs/atlas/alert-basics/)
- [Configure Alerts Webhooks](https://www.mongodb.com/docs/atlas/configure-alerts/)
- [Atlas Admin API - Alerts](https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Alerts)
