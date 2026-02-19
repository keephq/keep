def sanitize_alert(alert_raw: dict) -> dict:
    """
        Recursively sanitize alert data by removing null characters.
        The function could be used to remove/replace any unwanted characters
        from the alert data structure, ensuring that the data is clean and safe
        for further processing or storage.

        Args:
            alert_raw (dict): The raw alert data
    """
    if alert_raw is None:
        return None

    if not isinstance(alert_raw, dict):
        raise ValueError("Input must be a dictionary")

    def sanitize(value):
        if isinstance(value, str):
            return value.replace('\x00', '')
        elif isinstance(value, dict):
            return {k: sanitize(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [sanitize(i) for i in value]
        return value

    return sanitize(alert_raw)
