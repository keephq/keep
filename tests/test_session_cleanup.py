"""
Regression tests for SQLAlchemy session cleanup in background tasks.

When recover_strategy() and check_dismissal_expiry() are called from
process_watcher_task via run_in_executor (session=None), they create
sessions internally via get_session_sync(). These sessions must be
closed in a finally block to prevent connection pool exhaustion.

See: https://github.com/keephq/keep/issues/5496
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from keep.api.bl.dismissal_expiry_bl import DismissalExpiryBl
from keep.api.bl.maintenance_windows_bl import MaintenanceWindowsBl


class TestRecoverStrategySessionCleanup:
    """MaintenanceWindowsBl.recover_strategy session lifecycle tests."""

    @patch("keep.api.bl.maintenance_windows_bl.get_alerts_by_status", return_value=[])
    @patch(
        "keep.api.bl.maintenance_windows_bl.get_maintenance_windows_started",
        return_value=[],
    )
    @patch("keep.api.bl.maintenance_windows_bl.get_session_sync")
    def test_closes_session_when_created_internally(
        self, mock_get_session, mock_get_windows, mock_get_alerts
    ):
        """Session created via get_session_sync must be closed after execution."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        MaintenanceWindowsBl.recover_strategy(logger=logging.getLogger(__name__))

        mock_get_session.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("keep.api.bl.maintenance_windows_bl.get_alerts_by_status", return_value=[])
    @patch(
        "keep.api.bl.maintenance_windows_bl.get_maintenance_windows_started",
        return_value=[],
    )
    @patch("keep.api.bl.maintenance_windows_bl.get_session_sync")
    def test_does_not_close_caller_provided_session(
        self, mock_get_session, mock_get_windows, mock_get_alerts
    ):
        """When a caller provides a session, recover_strategy must not close it."""
        caller_session = MagicMock()

        MaintenanceWindowsBl.recover_strategy(
            logger=logging.getLogger(__name__), session=caller_session
        )

        mock_get_session.assert_not_called()
        caller_session.close.assert_not_called()

    @patch("keep.api.bl.maintenance_windows_bl.get_alerts_by_status")
    @patch(
        "keep.api.bl.maintenance_windows_bl.get_maintenance_windows_started",
        return_value=[],
    )
    @patch("keep.api.bl.maintenance_windows_bl.get_session_sync")
    def test_closes_session_on_exception(
        self, mock_get_session, mock_get_windows, mock_get_alerts
    ):
        """Session must be closed even when an exception occurs mid-execution."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_get_alerts.side_effect = RuntimeError("simulated DB error")

        with pytest.raises(RuntimeError, match="simulated DB error"):
            MaintenanceWindowsBl.recover_strategy(
                logger=logging.getLogger(__name__)
            )

        mock_session.close.assert_called_once()


class TestCheckDismissalExpirySessionCleanup:
    """DismissalExpiryBl.check_dismissal_expiry session lifecycle tests."""

    @patch(
        "keep.api.bl.dismissal_expiry_bl.DismissalExpiryBl.get_alerts_with_expired_dismissals",
        return_value=[],
    )
    @patch("keep.api.bl.dismissal_expiry_bl.get_session_sync")
    def test_closes_session_when_created_internally(
        self, mock_get_session, mock_get_expired
    ):
        """Session created via get_session_sync must be closed after execution."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        DismissalExpiryBl.check_dismissal_expiry(
            logger=logging.getLogger(__name__)
        )

        mock_get_session.assert_called_once()
        mock_session.close.assert_called_once()

    @patch(
        "keep.api.bl.dismissal_expiry_bl.DismissalExpiryBl.get_alerts_with_expired_dismissals",
        return_value=[],
    )
    @patch("keep.api.bl.dismissal_expiry_bl.get_session_sync")
    def test_does_not_close_caller_provided_session(
        self, mock_get_session, mock_get_expired
    ):
        """When a caller provides a session, check_dismissal_expiry must not close it."""
        caller_session = MagicMock()

        DismissalExpiryBl.check_dismissal_expiry(
            logger=logging.getLogger(__name__), session=caller_session
        )

        mock_get_session.assert_not_called()
        caller_session.close.assert_not_called()

    @patch(
        "keep.api.bl.dismissal_expiry_bl.DismissalExpiryBl.get_alerts_with_expired_dismissals"
    )
    @patch("keep.api.bl.dismissal_expiry_bl.get_session_sync")
    def test_closes_session_on_exception(
        self, mock_get_session, mock_get_expired
    ):
        """Session must be closed even when an exception occurs mid-execution."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_get_expired.side_effect = RuntimeError("simulated DB error")

        with pytest.raises(RuntimeError, match="simulated DB error"):
            DismissalExpiryBl.check_dismissal_expiry(
                logger=logging.getLogger(__name__)
            )

        mock_session.close.assert_called_once()
