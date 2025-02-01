import copy
import datetime
import json
import logging
import re
import urllib.parse
from datetime import timedelta
from itertools import groupby

import json5
import pytz
from dateutil import parser
from dateutil.parser import ParserError

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.db import get_alerts_by_fingerprint
from keep.api.models.alert import AlertStatus
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts

logger = logging.getLogger(__name__)

_len = len


def all(iterable) -> bool:
    # https://stackoverflow.com/questions/3844801/check-if-all-elements-in-a-list-are-identical
    g = groupby(iterable)
    return next(g, True) and not next(g, False)


def diff(iterable: iter) -> bool:
    # Opposite of all - returns True if any element is different
    return not all(iterable)


def len(iterable=[]) -> int:
    return _len(iterable)


def uppercase(string) -> str:
    return string.upper()


def lowercase(string) -> str:
    return string.lower()


def split(string, delimeter) -> list:
    return string.strip().split(delimeter)


def index(iterable, index) -> any:
    return iterable[index]


def strip(string) -> str:
    return string.strip()


def remove_newlines(string: str = "") -> str:
    return string.replace("\r\n", "").replace("\n", "").replace("\t", "")


def first(iterable):
    return iterable[0]


def last(iterable):
    return iterable[-1]


def utcnow() -> datetime.datetime:
    dt = datetime.datetime.now(datetime.timezone.utc)
    return dt


def utcnowtimestamp() -> int:
    return int(utcnow().timestamp())


def utcnowiso() -> str:
    return utcnow().isoformat()


def substract_minutes(dt: datetime.datetime, minutes: int) -> datetime.datetime:
    """
    Substract minutes from a datetime object

    Args:
        dt (datetime.datetime): The datetime object
        minutes (int): The number of minutes to substract

    Returns:
        datetime.datetime: The new datetime object
    """
    return dt - datetime.timedelta(minutes=minutes)


def to_utc(dt: datetime.datetime | str = "") -> datetime.datetime:
    if isinstance(dt, str):
        try:
            dt = parser.parse(dt.strip())
        except ParserError:
            # Failed to parse the date
            return ""
    utc_dt = dt.astimezone(pytz.utc)
    return utc_dt


def to_timestamp(dt: datetime.datetime | str = "") -> int:
    if isinstance(dt, str):
        try:
            dt = parser.parse(dt.strip())
        except ParserError:
            # Failed to parse the date
            return 0
    return int(dt.timestamp())


def datetime_compare(t1: datetime = None, t2: datetime = None) -> float:
    if not t1 or not t2:
        return 0
    diff = (t1 - t2).total_seconds() / 3600
    return diff


def json_dumps(data: str | dict) -> str:
    if isinstance(data, str):
        data = json.loads(data)
    return json.dumps(data, indent=4, default=str)


def json_loads(data: str) -> dict:
    def parse_bad_json(bad_json):
        # Remove or replace control characters
        control_char_regex = re.compile(r"[\x00-\x1f\x7f-\x9f]")

        def replace_control_char(match):
            char = match.group(0)
            return f"\\u{ord(char):04x}"

        cleaned_json = control_char_regex.sub(replace_control_char, bad_json)

        # Parse the cleaned JSON
        return json.loads(cleaned_json)

    # in most cases, we don't need escaping
    try:
        d = json.loads(data)
    except json.JSONDecodeError:
        try:
            d = parse_bad_json(data)
        except json.JSONDecodeError:
            logger.exception('Failed to parse "bad" JSON')
            d = {}
    # catch any other exceptions
    except Exception:
        logger.exception("Failed to parse JSON")
        d = {}

    return d


def replace(string: str, old: str, new: str) -> str:
    return string.replace(old, new)


def encode(string) -> str:
    return urllib.parse.quote(string)


def dict_to_key_value_list(d: dict) -> list:
    return [f"{k}:{v}" for k, v in d.items()]


def slice(str_to_slice: str, start: int = 0, end: int = 0) -> str:
    if end == 0 or end == "0":
        return str_to_slice[int(start) :]
    return str_to_slice[int(start) : int(end)]


def join(
    iterable: list | dict | str, delimiter: str = ",", prefix: str | None = None
) -> str:
    if isinstance(iterable, str):
        iterable = json5.loads(iterable)

    if isinstance(iterable, dict):
        if prefix:
            return delimiter.join([f"{prefix}{k}={v}" for k, v in iterable.items()])
        return delimiter.join([f"{k}={v}" for k, v in iterable.items()])

    if prefix:
        return delimiter.join([f"{prefix}{item}" for item in iterable])
    return delimiter.join([str(item) for item in iterable])


def dict_pop(data: str | dict, *args) -> dict:
    if isinstance(data, str):
        data = json.loads(data)
    dict_copy = copy.deepcopy(data)
    for arg in args:
        dict_copy.pop(arg, None)
    return dict_copy


def run_mapping(
    id: int, lst: str | list, search_key: str, matcher: str, key: str, **kwargs
) -> list:
    """
    Run a mapping rule by ID

    For example, given the following lst:
    [
        {"firstName": "John"},
        {"firstName": "Jane"}
    ]
    and the following mapping rule rows:
    [
            {"name": "John", "age": 30},
            {"name": "Jane", "age": 25}
    ]
    The following search_key, matcher and key:
    search_key = "firstName"
    matcher = "name"
    key = "age"
    The function will return: [30, 25]

    Args:
        id (int): The rule ID from the database
        lst (str | list): The list of dictionaries to search
        search_key (str): The key to search in the list
        matcher (str): The key to match in the mapping rule
        key (str): The key to return from the mapping rule

    Returns:
        list: The list of values from the mapping rule
    """
    if isinstance(lst, str):
        lst = lst.strip()
        from asteval import Interpreter

        aeval = Interpreter()
        lst = aeval(lst)

    if not lst:
        return []

    tenant_id = kwargs.get("tenant_id")
    if not tenant_id:
        return []

    enrichments_bl = EnrichmentsBl(tenant_id)
    result = enrichments_bl.run_mapping_rule_by_id(id, lst, search_key, matcher, key)
    return result


def add_time_to_date(date, date_format, time_str):
    """
    Add time to a date based on a given time string (e.g., '1w', '2d').

    Args:
        date (str or datetime.datetime): The date to which the time will be added.
        date_format (str): The format of the date string if the date is provided as a string.
        time_str (str): The time to add (e.g., '1w', '2d').

    Returns:
        datetime.datetime: The new datetime object with the added time.
    """
    if isinstance(date, str):
        date = datetime.datetime.strptime(date, date_format)

    time_units = {
        "w": "weeks",
        "d": "days",
        "h": "hours",
        "m": "minutes",
        "s": "seconds",
    }

    time_dict = {unit: 0 for unit in time_units.values()}

    matches = re.findall(r"(\d+)([wdhms])", time_str)
    for value, unit in matches:
        time_dict[time_units[unit]] += int(value)

    new_date = date + datetime.timedelta(**time_dict)
    return new_date


def get_firing_time(alert: dict, time_unit: str, **kwargs) -> str:
    """
    Get the firing time of an alert.

    Args:
        alert (dict): The alert dictionary.
        time_unit (str): The time unit to return the result in ('m', 's', or 'h').
        **kwargs: Additional keyword arguments.

    Returns:
        str: The firing time of the alert in the specified time unit.
    """
    tenant_id = kwargs.get("tenant_id")
    if not tenant_id:
        raise ValueError("tenant_id is required")

    try:
        alert = json.loads(alert) if isinstance(alert, str) else alert
    except Exception:
        raise ValueError("alert is not a valid JSON")

    fingerprint = alert.get("fingerprint")
    if not fingerprint:
        raise ValueError("fingerprint is required")

    alert_from_db = get_alerts_by_fingerprint(
        tenant_id=tenant_id,
        fingerprint=fingerprint,
        limit=1,
    )
    if alert_from_db:
        alert_dto = convert_db_alerts_to_dto_alerts(alert_from_db)[0]
        # if the alert is not firing, there is no start firing time
        if alert_dto.status != AlertStatus.FIRING.value:
            return "0.00"
        firing = datetime.datetime.now(
            tz=datetime.timezone.utc
        ) - datetime.datetime.fromisoformat(alert_dto.firingStartTime)
    else:
        return "0.00"

    if time_unit in ["m", "minutes"]:
        result = firing.total_seconds() / 60
    elif time_unit in ["h", "hours"]:
        result = firing.total_seconds() / 3600
    elif time_unit in ["s", "seconds"]:
        result = firing.total_seconds()
    else:
        raise ValueError(
            "Invalid time_unit. Use 'minutes', 'hours', 'seconds', 'm', 'h', or 's'."
        )

    return f"{result:.2f}"


def is_first_time(fingerprint: str, since: str = None, **kwargs) -> str:
    """
    Get the firing time of an alert.

    Args:
        alert (dict): The alert dictionary.
        **kwargs: Additional keyword arguments.

    Returns:
        str: The firing time of the alert in the specified time unit.
    """
    tenant_id = kwargs.get("tenant_id")
    if not tenant_id:
        raise ValueError("tenant_id is required")

    if not fingerprint:
        raise ValueError("fingerprint is required")

    prev_alerts = get_alerts_by_fingerprint(
        tenant_id=tenant_id, fingerprint=fingerprint, limit=2, status="firing"
    )

    if not prev_alerts:
        # this should not happen since workflows are running only after the alert is saved in the database
        raise ValueError("No previous alerts found for the given fingerprint.")

    # if there is only one alert, it is the first time 100%
    if len(prev_alerts) == 1:
        return True
    # if there is more than one alert and no 'since' specified, it is not the first time
    elif not since:
        return False

    # since is "24h" or "1d" or "1w" etc.
    prevAlert = prev_alerts[1]

    if since[-1] == "d":
        time_delta = timedelta(days=int(since[:-1]))
    elif since[-1] == "w":
        time_delta = timedelta(weeks=int(since[:-1]))
    elif since[-1] == "h":
        time_delta = timedelta(hours=int(since[:-1]))
    elif since[-1] == "m":
        time_delta = timedelta(minutes=int(since[:-1]))
    else:
        raise ValueError("Invalid time unit. Use 'm', 'h', 'd', or 'w'.")

    current_time = datetime.datetime.utcnow()
    if current_time - prevAlert.timestamp > time_delta:
        return True
    else:
        return False


def is_business_hours(
    time_to_check=None,
    start_hour=8,
    end_hour=20,
    business_days=(0, 1, 2, 3, 4),  # Mon = 0, Sun = 6
    timezone="UTC",
):
    """
    Check if the given time or current time is between start_hour and end_hour
    and falls on a business day

    Args:
        time_to_check (str | datetime.datetime, optional): Time to check.
            If None, current UTC time will be used.
        start_hour (int, optional): Start hour in 24-hour format. Defaults to 8 (8:00 AM)
        end_hour (int, optional): End hour in 24-hour format. Defaults to 20 (8:00 PM)
        business_days (tuple, optional): Days of week considered as business days.
            Monday=0 through Sunday=6. Defaults to Mon-Fri (0,1,2,3,4)
        timezone (str, optional): Timezone name (e.g., 'UTC', 'America/New_York', 'Europe/London').
            Defaults to 'UTC'.

    Returns:
        bool: True if time is between start_hour and end_hour on a business day

    Raises:
        ValueError: If start_hour or end_hour are not between 0 and 23
        ValueError: If business_days contains invalid day numbers
        ValueError: If timezone string is invalid
    """
    # Validate hour inputs
    start_hour = int(start_hour)
    end_hour = int(end_hour)
    if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23):
        raise ValueError("Hours must be between 0 and 23")

    # Strict validation for business_days
    try:
        invalid_days = [day for day in business_days if not (0 <= day <= 6)]
        if invalid_days:
            raise ValueError(
                f"Invalid business days: {invalid_days}. Days must be between 0 (Monday) and 6 (Sunday)"
            )
    except TypeError:
        raise ValueError(
            "business_days must be an iterable of integers between 0 and 6"
        )

    # Validate and convert timezone string to pytz timezone
    try:
        tz = pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(f"Invalid timezone: {timezone}")

    # If no time provided, use current UTC time
    if time_to_check is None:
        dt = utcnow()
    else:
        # Convert string to datetime if needed
        dt = to_utc(time_to_check) if isinstance(time_to_check, str) else time_to_check

    if not dt:  # Handle case where parsing failed
        return False

    # Convert to specified timezone
    dt = dt.astimezone(tz)

    # Get weekday (Monday = 0, Sunday = 6)
    weekday = dt.weekday()

    # Check if it's a business day
    if weekday not in business_days:
        return False

    # Get just the hour (in 24-hour format)
    hour = dt.hour

    # Check if hour is between start_hour and end_hour
    return start_hour <= hour < end_hour


def dictget(data: str | dict, key: str, default: any = None) -> any:
    """
    Get a value from a dictionary with a default fallback.

    Args:
        data (str | dict): The dictionary to search in. Can be a JSON string or dict.
        key (str): The key to look up
        default (any): The default value to return if key is not found

    Returns:
        any: The value found in the dictionary or the default value

    Example:
        >>> d = {"s1": "critical", "s2": "error"}
        >>> dictget(d, "s1", "info")
        'critical'
        >>> dictget(d, "s3", "info")
        'info'
    """
    if isinstance(data, str):
        try:
            data = json_loads(data)
        except Exception:
            return default

    if not isinstance(data, dict):
        return default

    return data.get(key, default)
