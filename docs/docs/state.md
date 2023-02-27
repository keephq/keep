---
sidebar_label: State
sidebar_position: 6
---

## Intro
Keep support state to support throttling mechanism's and track alerts over time.

It currently do so by holding the state using a `keepstate.json` file, which can be overrided by `KEEP_STATE_FILE` environment variable.

## How to use
The current usage of Keep's state mechanism is [throttling](docs/../throttles/what-is-throttle.md).
Keep handles it for you behind the scenes so you can use it without doing any modifications.

If you are running Keep on production, you should host the `keepstate.json` file on persistance storage and mount it to your serverless environment. Feel free to create an issue if you need solution for your preferred deployment architecture.

## Keep state structure
An example for a simple state file:
```
{
    "service-is-up": [
        {
            "alert_status": "resolved",
            "alert_context": {
                "alert_id": "service-is-up",
                "alert_owners": [],
                "alert_tags": []
            }
        }
    ]
}
```

## Roadmap

Keep's roadmap around state:
- Saving state in DB (starts with SQLite and PostgreSQL).
- Hosting the state in buckets (AWS, GCP and Azure).
- Enriching state with more context so throttling mechanism would be flexer.
- More deployment options (support serverless architectures).

Feel free to reach out (by creating issues or whatever you prefer) so have impact on this roadmap!
