---
sidebar_label: State
sidebar_position: 6
---

# State

## Intro
Keep State Manager currently used for:
1. Throttling
2. Track alerts over time

It's currently doing so by simply holding the state using a `keepstate.json` file, which can be overrided by `KEEP_STATE_FILE` environment variable.

## Example
One of the usages for Keep's state mechanism is throttling, see [One Until Resolved](docs/../throttles/one-until-resolved.md). Keep handles it for you behind the scenes so you can use it without doing any further modifications.

## Serverless
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

### Roadmap

Keep's roadmap around state (great first issues):
- Saving state in a database.
- Hosting state in buckets (AWS, GCP and Azure -> read/write).
- Enriching state with more context so throttling mechanism would be flexer.
