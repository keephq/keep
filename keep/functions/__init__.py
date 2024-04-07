import copy
import datetime
import json
import urllib.parse
from itertools import groupby

import pytz
from dateutil import parser

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


def to_utc(dt: datetime.datetime | str) -> datetime.datetime:
    if isinstance(dt, str):
        dt = parser.parse(dt)
    utc_dt = dt.astimezone(pytz.utc)
    return utc_dt


def datetime_compare(t1, t2) -> float:
    diff = (t1 - t2).total_seconds() / 3600
    return diff


def json_dumps(data: str | dict) -> str:
    if isinstance(data, str):
        data = json.loads(data)
    return json.dumps(data, indent=4, default=str)


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
