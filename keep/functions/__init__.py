import copy
import datetime
import json
import re
import urllib.parse
from itertools import groupby

import pytz
from dateutil import parser
from dateutil.parser import ParserError

from keep.api.bl.enrichments import EnrichmentsBl

_len = len
_all = all


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


def datetime_compare(t1: datetime = None, t2: datetime = None) -> float:
    if t1 is None or t2 is None:
        return 0
    diff = (t1 - t2).total_seconds() / 3600
    return diff


def json_dumps(data: str | dict) -> str:
    if isinstance(data, str):
        data = json.loads(data)
    return json.dumps(data, indent=4, default=str)


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
