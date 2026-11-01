"""Parse Site24x7 webhook tags without retaining mutable payload references."""


def parse_tags(raw: object) -> dict:
    """Accept comma-separated tags or a mapping; ignore empty tag names.

    Split key/value tags only at the first colon. Bare tags use their name as
    the value. Later duplicate names replace earlier values, as in a dict.
    Mapping values are preserved, but the outer mapping is copied.
    """
    if isinstance(raw, dict):
        return {key: value for key, value in raw.items() if key != ""}
    if not isinstance(raw, str):
        return {}
    labels = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        key, separator, value = item.partition(":")
        key = key.strip()
        if key:
            labels[key] = value.strip() if separator else key
    return labels
