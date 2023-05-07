import pytest

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
