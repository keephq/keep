from datetime import datetime

from keep.api.models.alert import AlertDto


def javascript_iso_format(last_received: str) -> str:
    """
    https://stackoverflow.com/a/63894149/12012756
    """
    dt = datetime.fromisoformat(last_received)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_and_enrich_deleted_and_assignees(alert: AlertDto, enrichments: dict):
    # tb: we'll need to refactor this at some point since its flaky
    # assignees and deleted are special cases that we need to handle
    # they are kept as a list of timestamps and we need to check if the
    # timestamp of the alert is in the list, if it is, it means that the
    # alert at that specific time was deleted or assigned.
    #
    # THIS IS MAINLY BECAUSE WE ALSO HAVE THE PULLED ALERTS,
    # OTHERWISE, WE COULD'VE JUST UPDATE THE ALERT IN THE DB
    deleted_last_received = enrichments.get(
        "deletedAt", enrichments.get("deleted", [])
    )  # "deleted" is for backward compatibility
    if javascript_iso_format(alert.lastReceived) in deleted_last_received:
        alert.deleted = True
    assignees: dict = enrichments.get("assignees", {})
    assignee = assignees.get(alert.lastReceived) or assignees.get(
        javascript_iso_format(alert.lastReceived)
    )
    if assignee:
        alert.assignee = assignee
