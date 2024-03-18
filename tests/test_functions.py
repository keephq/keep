import datetime

import pytest
import pytz

import keep.functions as functions


@pytest.mark.parametrize(
    "test_description, given, expected",
    [
        # lists
        ("list with different items", [11, 12, 13, "a", "b"], True),
        ("list with sequential duplicates", ["a", "a"], False),
        ("list of case insensitive duplicates", ["a", "A"], True),
        ("list of sequential int duplicates", [42, 42], False),
        # tuples
        ("tulple of different items", ("alpha", "beta"), True),
        # sets
        ("sets should always be False if there are no differences", {1, 1, 1}, False),
        ("sets should be True if there are differences", {1, 1, 1, 2}, True),
        # strings
        ("a string is an iterator in Python", "string", True),
        ("a string with repeating letters", "gg", False),
        # boolean
        ("list with same False boolean", [False, False, False], False),
        ("list with same True boolean", [True, True, True], False),
        ("list with mixed booleans", [True, False, True], True),
        # !!! Interesting results when Python booleans are in iterators !!!
        ("lists with strings and boolean True", ["a", True, "a"], True),
        # !!! empty iterator !!!
        ("empty list", [], False),
    ],
)

def test_functions_diff(test_description, given, expected):
    assert (
        functions.diff(given) == expected
    ), f"{test_description}: Expected {given} to return {expected}"

def test_keep_len_function():
    """
    Test the len function
    """
    assert functions.len([1, 2, 3]) == 3

def test_keep_all_function():
    """
    Test the all function
    """
    assert functions.all([1, 1, 1]) == True
    assert functions.all([1, 1, 0]) == False

def test_keep_diff_function():
    """
    Test the diff function
    """
    assert functions.diff([1, 1, 1]) == False
    assert functions.diff([1, 1, 0]) == True

def test_keep_split_function():
    """
    Test the split function
    """
    assert functions.split("a,b,c", ",") == ["a", "b", "c"]
    assert functions.split("a|b|c", "|") == ["a", "b", "c"]

def test_keep_uppercase_function():
    """
    Test the uppercase function
    """
    assert functions.uppercase("a") == "A"

def test_keep_lowercase_function():
    """
    Test the lowercase function
    """
    assert functions.lowercase("A") == "a"

def test_keep_strip_function():
    """
    Test the strip function
    """
    assert functions.strip("  a  ") == "a"

def test_keep_first_function():
    """
    Test the first function
    """
    assert functions.first([1, 2, 3]) == 1

def test_keep_last_function():
    """
    Test the last function
    """
    assert functions.last([1, 2, 3]) == 3

def test_keep_utcnow_function():
    """
    Test the utcnow function
    """
    dt = functions.utcnow()
    assert isinstance(dt.tzinfo, type(datetime.timezone.utc))
    assert isinstance(dt, datetime.datetime)

def test_keep_to_utc_function():
    """
    Test the to_utc function
    """
    dt = functions.to_utc("2021-01-01 00:00:00")
    assert dt.tzinfo == pytz.utc
    assert isinstance(dt, datetime.datetime)
    now = datetime.datetime.now()
    now_utc = functions.to_utc(now)
    assert now_utc.tzinfo == pytz.utc

def test_keep_datetime_compare_function():
    """
    Test the datetime_compare function
    """
    dt1 = datetime.datetime.now()
    dt2 = datetime.datetime.now() + datetime.timedelta(hours=1)
    assert int(functions.datetime_compare(dt1, dt2)) == -1
    assert int(functions.datetime_compare(dt2, dt1)) == 1
    assert int(functions.datetime_compare(dt1, dt1)) == 0

def test_keep_encode_function():
    """
    Test the encode function
    """
    assert functions.encode("a b") == "a%20b"
