import datetime
import urllib.parse
from itertools import groupby

import pytz
from dateutil import parser

_len = len
_all = all


def all(iterable):
    # https://stackoverflow.com/questions/3844801/check-if-all-elements-in-a-list-are-identical
    g = groupby(iterable)
    return next(g, True) and not next(g, False)


def diff(iterable: iter) -> bool:
    # Opposite of all - returns True if any element is different
    return not all(iterable)


def len(iterable=[]):
    return _len(iterable)


def split(string, delimeter):
    return string.strip().split(delimeter)


def strip(string):
    return string.strip()


def first(iterable):
    return iterable[0]


def utcnow():
    dt = datetime.datetime.now(datetime.timezone.utc)
    return dt


def to_utc(dt: datetime.datetime | str):
    if isinstance(dt, str):
        dt = parser.parse(dt)
    utc_dt = dt.astimezone(pytz.utc)
    return utc_dt


def datetime_compare(t1, t2):
    return (t1 - t2).total_seconds() / 3600


def encode(string):
    return urllib.parse.quote(string)
