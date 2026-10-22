"""Tests for is_business_hours midnight-crossing window (issue #6780).

When start_hour > end_hour the window wraps midnight:
    start_hour=20, end_hour=8  →  covers 20:00–07:59 of the *same calendar run*.

The business-day filter still applies; all tests use a Monday to stay on the
default Mon-Fri weekday set.
"""

import datetime

import pytest
import pytz

from keep.functions import is_business_hours


# 2024-01-01 is a Monday.
_MON = datetime.datetime(2024, 1, 1, tzinfo=pytz.utc)


def _monday_at(hour: int) -> datetime.datetime:
    """Return a UTC datetime for the given hour on a Monday."""
    return _MON.replace(hour=hour, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Overnight / midnight-crossing windows  (start_hour > end_hour)
# ---------------------------------------------------------------------------


def test_overnight_window_hour_after_start_returns_true():
    """22:00 is within a 20-08 overnight window."""
    assert is_business_hours(_monday_at(22), start_hour=20, end_hour=8) is True


def test_overnight_window_hour_at_midnight_returns_true():
    """00:00 is within a 20-08 overnight window."""
    assert is_business_hours(_monday_at(0), start_hour=20, end_hour=8) is True


def test_overnight_window_hour_before_end_returns_true():
    """02:00 is within a 20-08 overnight window."""
    assert is_business_hours(_monday_at(2), start_hour=20, end_hour=8) is True


def test_overnight_window_hour_at_start_boundary_returns_true():
    """20:00 exactly is the first included hour."""
    assert is_business_hours(_monday_at(20), start_hour=20, end_hour=8) is True


def test_overnight_window_hour_at_end_boundary_excluded():
    """08:00 is the first *excluded* hour (half-open [start, end))."""
    assert is_business_hours(_monday_at(8), start_hour=20, end_hour=8) is False


def test_overnight_window_midday_excluded():
    """12:00 is well outside the 20-08 overnight window."""
    assert is_business_hours(_monday_at(12), start_hour=20, end_hour=8) is False


# ---------------------------------------------------------------------------
# Same-day windows should not regress
# ---------------------------------------------------------------------------


def test_same_day_window_in_range():
    """14:00 is within 09-17."""
    assert is_business_hours(_monday_at(14), start_hour=9, end_hour=17) is True


def test_same_day_window_before_start():
    """08:00 is before 09-17."""
    assert is_business_hours(_monday_at(8), start_hour=9, end_hour=17) is False


def test_same_day_window_at_end_excluded():
    """17:00 is the first excluded hour for 09-17."""
    assert is_business_hours(_monday_at(17), start_hour=9, end_hour=17) is False
