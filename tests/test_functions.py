import datetime
import json
from datetime import timedelta

import pytest
import pytz
from freezegun import freeze_time

import keep.functions as functions
from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertStatus
from keep.api.models.db.alert import AlertActionType


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


def test_len():
    assert functions.len([1, 2, 3]) == 3
    assert functions.len([]) == 0


def test_all():
    assert functions.all([True, True, True]) is True
    assert functions.all([True, False, True]) is False


def test_diff():
    assert functions.diff([1, 1, 1]) is False
    assert functions.diff([1, 2, 1]) is True


def test_uppercase():
    assert functions.uppercase("test") == "TEST"


def test_lowercase():
    assert functions.lowercase("TEST") == "test"


def test_split():
    assert functions.split("a,b,c", ",") == ["a", "b", "c"]


def test_strip():
    assert functions.strip("  test  ") == "test"


def test_first():
    assert functions.first([1, 2, 3]) == 1


def test_last():
    assert functions.last([1, 2, 3]) == 3


def test_utcnow():
    now = datetime.datetime.now(datetime.timezone.utc)
    func_now = functions.utcnow()
    # Assuming this test runs quickly, the two times should be within a few seconds of each other
    assert (func_now - now).total_seconds() < 5


def test_utcnowiso():
    assert isinstance(functions.utcnowiso(), str)


def test_substract_minutes():
    now = datetime.datetime.now(datetime.timezone.utc)
    earlier = functions.substract_minutes(now, 10)
    assert (now - earlier).total_seconds() == 600  # 10 minutes


def test_to_utc():
    local_dt = datetime.datetime.now()
    utc_dt = functions.to_utc(local_dt)
    # Compare the timezone names instead of the timezone objects
    assert utc_dt.tzinfo.tzname(utc_dt) == datetime.timezone.utc.tzname(None)


def test_datetime_compare():
    dt1 = datetime.datetime.now(datetime.timezone.utc)
    dt2 = functions.substract_minutes(dt1, 60)  # 1 hour earlier
    assert functions.datetime_compare(dt1, dt2) == 1


def test_json_dumps():
    data = {"key": "value"}
    expected = json.dumps(data, indent=4, default=str)
    assert functions.json_dumps(data) == expected


def test_encode():
    assert functions.encode("test value") == "test%20value"


def test_dict_to_key_value_list():
    assert functions.dict_to_key_value_list({"a": 1, "b": "test"}) == ["a:1", "b:test"]


def test_dict_pop():
    d = {"a": 1, "b": 2}
    d2 = functions.dict_pop(d, "a")
    assert d2 == {"b": 2}


def test_dict_pop_str():
    d = '{"a": 1, "b": 2}'
    d2 = functions.dict_pop(d, "a")
    assert d2 == {"b": 2}


def test_slice():
    assert functions.slice("long string", 0, 4) == "long"


def test_slice_no_end():
    assert functions.slice("long string", 5) == "string"


def test_index():
    assert functions.index([1, 2, 3], 2) == 3


def test_index_2():
    s = "prod-group-a-service-b-high-cpu"
    assert functions.index(functions.split(s, "-"), 0) == "prod"
    assert functions.index(functions.split(s, "-"), 1) == "group"
    assert functions.index(functions.split(s, "-"), 2) == "a"
    assert functions.index(functions.split(s, "-"), 3) == "service"
    assert functions.index(functions.split(s, "-"), 4) == "b"
    assert functions.index(functions.split(s, "-"), 5) == "high"
    assert functions.index(functions.split(s, "-"), 6) == "cpu"


def test_add_time_to_date():
    """
    Test the add_time_to_date function
    """
    date_str = "2024-07-01"
    date_format = "%Y-%m-%d"

    # Test adding 1 week
    time_str = "1w"
    expected_date = datetime.datetime(2024, 7, 8)
    assert functions.add_time_to_date(date_str, date_format, time_str) == expected_date

    # Test adding 2 days
    time_str = "2d"
    expected_date = datetime.datetime(2024, 7, 3)
    assert functions.add_time_to_date(date_str, date_format, time_str) == expected_date

    # Test adding 3 hours
    time_str = "3h"
    expected_date = datetime.datetime(2024, 7, 1, 3, 0)
    assert functions.add_time_to_date(date_str, date_format, time_str) == expected_date

    # Test adding 30 minutes
    time_str = "30m"
    expected_date = datetime.datetime(2024, 7, 1, 0, 30)
    assert functions.add_time_to_date(date_str, date_format, time_str) == expected_date

    # Test adding 1 week, 2 days, 3 hours, and 30 minutes
    time_str = "1w 2d 3h 30m"
    expected_date = datetime.datetime(2024, 7, 10, 3, 30)
    assert functions.add_time_to_date(date_str, date_format, time_str) == expected_date


def test_add_time_to_date_with_datetime_string():
    """
    Test the add_time_to_date function with a specific datetime string input
    """
    date_str = "2024-08-16T14:21:00.000-0500"
    date_format = "%Y-%m-%dT%H:%M:%S.%f%z"

    # Test adding 1 day
    time_str = "1d"
    expected_date = datetime.datetime(
        2024, 8, 17, 14, 21, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))
    )
    assert functions.add_time_to_date(date_str, date_format, time_str) == expected_date

    # Test adding 2 weeks
    time_str = "2w"
    expected_date = datetime.datetime(
        2024, 8, 30, 14, 21, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))
    )
    assert functions.add_time_to_date(date_str, date_format, time_str) == expected_date

    # Test adding 3 hours
    time_str = "3h"
    expected_date = datetime.datetime(
        2024, 8, 16, 17, 21, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))
    )
    assert functions.add_time_to_date(date_str, date_format, time_str) == expected_date

    # Test adding 45 minutes
    time_str = "45m"
    expected_date = datetime.datetime(
        2024, 8, 16, 15, 6, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))
    )
    assert functions.add_time_to_date(date_str, date_format, time_str) == expected_date

    # Test adding 1 week, 1 day, 1 hour, and 1 minute
    time_str = "1w 1d 1h 1m"
    expected_date = datetime.datetime(
        2024, 8, 24, 15, 22, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))
    )
    assert functions.add_time_to_date(date_str, date_format, time_str) == expected_date


def test_get_firing_time_case1(create_alert):
    fingerprint = "fp1"
    base_time = datetime.datetime.now(tz=pytz.utc)

    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=90))
    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=60))
    create_alert(fingerprint, AlertStatus.RESOLVED, base_time - timedelta(minutes=30))
    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=15))

    alert = {"fingerprint": fingerprint}
    result = functions.get_firing_time(alert, "m", tenant_id=SINGLE_TENANT_UUID)
    assert abs(float(result) - 15.0) < 1  # Allow for small time differences


def test_get_firing_time_case2(create_alert):
    fingerprint = "fp2"
    base_time = datetime.datetime.now(tz=pytz.utc)

    create_alert(fingerprint, AlertStatus.RESOLVED, base_time - timedelta(minutes=90))
    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=30))
    create_alert(fingerprint, AlertStatus.RESOLVED, base_time)

    alert = {"fingerprint": fingerprint}
    assert functions.get_firing_time(alert, "m", tenant_id=SINGLE_TENANT_UUID) == "0.00"


def test_get_firing_time_case3(create_alert):
    fingerprint = "fp3"
    base_time = datetime.datetime.now(tz=pytz.utc)

    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=120))
    create_alert(fingerprint, AlertStatus.RESOLVED, base_time - timedelta(minutes=90))
    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=30))
    create_alert(fingerprint, AlertStatus.FIRING, base_time)

    alert = {"fingerprint": fingerprint}
    result = functions.get_firing_time(alert, "m", tenant_id=SINGLE_TENANT_UUID)
    assert abs(float(result) - 30.0) < 1  # Allow for small time differences


def test_get_firing_time_case4(create_alert):
    fingerprint = "fp4"
    base_time = datetime.datetime.now(tz=pytz.utc)

    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=150))
    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=120))
    create_alert(fingerprint, AlertStatus.RESOLVED, base_time - timedelta(minutes=90))
    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=60))
    create_alert(fingerprint, AlertStatus.RESOLVED, base_time - timedelta(minutes=30))
    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=15))

    alert = {"fingerprint": fingerprint}
    result = functions.get_firing_time(alert, "m", tenant_id=SINGLE_TENANT_UUID)
    assert abs(float(result) - 15.0) < 1  # Allow for small time differences


def test_get_firing_time_no_firing(create_alert):
    fingerprint = "fp5"
    base_time = datetime.datetime.now(tz=pytz.utc)

    create_alert(fingerprint, AlertStatus.RESOLVED, base_time - timedelta(minutes=60))
    create_alert(fingerprint, AlertStatus.RESOLVED, base_time - timedelta(minutes=30))
    create_alert(fingerprint, AlertStatus.RESOLVED, base_time)

    alert = {"fingerprint": fingerprint}
    assert functions.get_firing_time(alert, "m", tenant_id=SINGLE_TENANT_UUID) == "0.00"


def test_get_firing_time_other_statuses(create_alert):
    fingerprint = "fp6"
    base_time = datetime.datetime.now(tz=pytz.utc)

    create_alert(fingerprint, AlertStatus.RESOLVED, base_time - timedelta(minutes=90))
    create_alert(fingerprint, AlertStatus.SUPPRESSED, base_time - timedelta(minutes=60))
    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=45))
    create_alert(
        fingerprint, AlertStatus.ACKNOWLEDGED, base_time - timedelta(minutes=30)
    )

    alert = {"fingerprint": fingerprint}
    result = functions.get_firing_time(alert, "m", tenant_id=SINGLE_TENANT_UUID)
    assert abs(float(result)) < 1  # Allow for small time differences


def test_get_firing_time_minutes_and_seconds(create_alert):
    fingerprint = "fp7"
    base_time = datetime.datetime.now(tz=pytz.utc)

    create_alert(fingerprint, AlertStatus.RESOLVED, base_time - timedelta(minutes=5))
    create_alert(
        fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=2, seconds=30)
    )
    create_alert(fingerprint, AlertStatus.FIRING, base_time)

    alert = {"fingerprint": fingerprint}
    result = functions.get_firing_time(alert, "s", tenant_id=SINGLE_TENANT_UUID)
    assert (
        abs(float(result) - 150.0) < 5  # seconds
    )  # Allow for small time differences (150 seconds = 2.5 minutes)


def test_first_time(create_alert):
    fingerprint = "fp1"
    base_time = datetime.datetime.now(tz=pytz.utc)
    create_alert(fingerprint, AlertStatus.FIRING, base_time)

    result = functions.is_first_time(fingerprint, tenant_id=SINGLE_TENANT_UUID)
    assert result == True

    create_alert(fingerprint, AlertStatus.FIRING, base_time)
    result = functions.is_first_time(fingerprint, tenant_id=SINGLE_TENANT_UUID)
    assert result == False


def test_first_time_with_since(create_alert):
    fingerprint = "fp2"
    base_time = datetime.datetime.now(tz=pytz.utc)

    create_alert(
        fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=24 * 60 + 1)
    )
    create_alert(fingerprint, AlertStatus.FIRING, base_time)

    result = functions.is_first_time(fingerprint, "24h", tenant_id=SINGLE_TENANT_UUID)
    assert result == True

    create_alert(
        fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=24 * 60 - 1)
    )
    result = functions.is_first_time(fingerprint, "24h", tenant_id=SINGLE_TENANT_UUID)
    assert result == False

    create_alert(
        fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=12 * 60 - 1)
    )
    result = functions.is_first_time(fingerprint, "12h", tenant_id=SINGLE_TENANT_UUID)
    assert result == False
    result = functions.is_first_time(fingerprint, "6h", tenant_id=SINGLE_TENANT_UUID)
    assert result == True


def test_firing_time_with_manual_resolve(create_alert):
    fingerprint = "fp10"
    base_time = datetime.datetime.now(tz=pytz.utc)

    # Alert fired 60 minutes ago
    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=60))
    # It was manually resolved
    enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID)
    enrichment_bl.enrich_alert(
        fingerprint=fingerprint,
        enrichments={"status": "resolved"},
        dispose_on_new_alert=True,
        action_type=AlertActionType.GENERIC_ENRICH,
        action_callee="tests",
        action_description="tests",
    )
    alert = {"fingerprint": fingerprint}
    result = functions.get_firing_time(alert, "m", tenant_id=SINGLE_TENANT_UUID)
    assert abs(float(result) - 0) < 1  # Allow for small time differences

    # Now its firing again, the firing time should be calculated from the last firing
    create_alert(fingerprint, AlertStatus.FIRING, base_time - timedelta(minutes=30))
    # It should override the dispoable status, but show only the time since the last firing
    result = functions.get_firing_time(alert, "m", tenant_id=SINGLE_TENANT_UUID)
    assert abs(float(result) - 30) < 1  # Allow for small time differences


def test_is_business_hours():
    """
    Test the default business hours (8-20) with different times
    """
    # Test during business hours
    business_time = datetime.datetime(
        2024, 3, 27, 14, 30, tzinfo=datetime.timezone.utc
    )  # 14:30
    assert functions.is_business_hours(business_time) == True

    # Test before business hours
    early_time = datetime.datetime(
        2024, 3, 27, 7, 30, tzinfo=datetime.timezone.utc
    )  # 7:30
    assert functions.is_business_hours(early_time) == False

    # Test after business hours
    late_time = datetime.datetime(
        2024, 3, 27, 20, 30, tzinfo=datetime.timezone.utc
    )  # 20:30
    assert functions.is_business_hours(late_time) == False

    # Test exactly at start hour
    start_time = datetime.datetime(
        2024, 3, 27, 8, 0, tzinfo=datetime.timezone.utc
    )  # 8:00
    assert functions.is_business_hours(start_time) == True

    # Test exactly at end hour
    end_time = datetime.datetime(
        2024, 3, 27, 20, 0, tzinfo=datetime.timezone.utc
    )  # 20:00
    assert functions.is_business_hours(end_time) == False


def test_is_business_hours_custom_hours():
    """
    Test custom business hours (9-17)
    """
    test_time = datetime.datetime(
        2024, 3, 27, 8, 30, tzinfo=datetime.timezone.utc
    )  # 8:30
    assert functions.is_business_hours(test_time, start_hour=9, end_hour=17) == False

    test_time = datetime.datetime(
        2024, 3, 27, 12, 30, tzinfo=datetime.timezone.utc
    )  # 12:30
    assert functions.is_business_hours(test_time, start_hour=9, end_hour=17) == True


def test_is_business_hours_invalid_hours():
    """
    Test with invalid hour inputs
    """
    test_time = datetime.datetime(2024, 3, 27, 12, 30, tzinfo=datetime.timezone.utc)

    with pytest.raises(ValueError):
        functions.is_business_hours(test_time, start_hour=24, end_hour=17)

    with pytest.raises(ValueError):
        functions.is_business_hours(test_time, start_hour=8, end_hour=-1)


def test_is_business_hours_string_input():
    """
    Test with string datetime input
    """
    assert functions.is_business_hours("2024-03-27T14:30:00Z") == True
    assert functions.is_business_hours("2024-03-27T06:30:00Z") == False


def test_is_business_hours_invalid_string():
    """
    Test with invalid string datetime input
    """
    assert functions.is_business_hours("invalid datetime") == False


def test_is_business_hours_no_params():
    """
    Test with no parameters by mocking the current time
    """
    # Test during business hours
    with freeze_time("2024-03-27 10:00:00"):
        assert functions.is_business_hours() == True

    # Test before business hours
    with freeze_time("2024-03-27 06:00:00"):
        assert functions.is_business_hours() == False

    # Test after business hours
    with freeze_time("2024-03-27 22:00:00"):
        assert functions.is_business_hours() == False

    # Test at the boundaries
    with freeze_time("2024-03-27 08:00:00"):
        assert functions.is_business_hours() == True

    with freeze_time("2024-03-27 19:59:59"):
        assert functions.is_business_hours() == True
