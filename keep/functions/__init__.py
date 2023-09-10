import datetime
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


def split(string, delimeter) -> list:
    return string.strip().split(delimeter)


def strip(string) -> str:
    return string.strip()


def first(iterable):
    return iterable[0]


def utcnow() -> datetime.datetime:
    dt = datetime.datetime.now(datetime.timezone.utc)
    return dt


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


def encode(string) -> str:
    return urllib.parse.quote(string)
