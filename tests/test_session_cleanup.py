"""
Regression tests for SQLAlchemy session cleanup in background tasks.

When recover_strategy() and check_dismissal_expiry() are called from
process_watcher_task via run_in_executor (session=None), they create
sessions internally via get_session_sync(). These sessions must be
closed in a finally block to prevent connection pool exhaustion.

See: https://github.com/keephq/keep/issues/5496

EnrichmentsBl has the same get_session_sync()-without-close pattern,
but the session lives on the instance across multiple method calls
instead of a single function body, and it's instantiated from ~15
call sites across routes/providers/tasks - some pass in a caller-owned
session, most don't. See TestEnrichmentsBlSessionCleanup below.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from sqlmodel import Session as SQLModelSession

from keep.api.bl.dismissal_expiry_bl import DismissalExpiryBl
from keep.api.bl.enrichments_bl import EnrichmentsBl
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


class TestEnrichmentsBlSessionCleanup:
    """
    EnrichmentsBl session lifecycle tests. EnrichmentsBl.__init__ does
    `self.db_session = db or get_session_sync()` with no corresponding
    close() anywhere in the class - callers that construct it with no
    `db` argument (the majority of call sites) leaked the connection
    until EnrichmentsBl.close()/__enter__/__exit__ were added.
    """

    @patch("keep.api.bl.enrichments_bl.get_session_sync")
    def test_closes_session_when_created_internally(self, mock_get_session):
        """A self-created session must be closed by close()."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        bl = EnrichmentsBl(tenant_id="test_tenant")
        bl.close()

        mock_get_session.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("keep.api.bl.enrichments_bl.get_session_sync")
    def test_does_not_close_caller_provided_session(self, mock_get_session):
        """A caller-provided session must never be closed by EnrichmentsBl."""
        caller_session = MagicMock()

        bl = EnrichmentsBl(tenant_id="test_tenant", db=caller_session)
        # close() may be called defensively by a caller that doesn't know
        # whether the session was self-created - it must still be a no-op.
        bl.close()
        bl.close()

        mock_get_session.assert_not_called()
        caller_session.close.assert_not_called()

    @patch("keep.api.bl.enrichments_bl.get_session_sync")
    def test_close_is_idempotent(self, mock_get_session):
        """Calling close() more than once must not double-close the session."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        bl = EnrichmentsBl(tenant_id="test_tenant")
        bl.close()
        bl.close()

        mock_session.close.assert_called_once()

    @patch("keep.api.bl.enrichments_bl.get_session_sync")
    def test_context_manager_closes_only_owned_session(self, mock_get_session):
        """`with EnrichmentsBl(...)` must close an owned session, but never
        a caller-provided one."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        with EnrichmentsBl(tenant_id="test_tenant") as bl:
            assert bl.db_session is mock_session
        mock_session.close.assert_called_once()

        caller_session = MagicMock()
        with EnrichmentsBl(tenant_id="test_tenant", db=caller_session):
            pass
        caller_session.close.assert_not_called()

    def test_close_releases_connection_back_to_pool(self, tmp_path, monkeypatch):
        """
        Exercise the actual production failure mechanism with a real
        SQLAlchemy engine/pool, not just a MagicMock: close() must return
        the checked-out connection to the pool, not just call a mock.
        """
        engine = create_engine(
            f"sqlite:///{tmp_path / 'test.db'}",
            poolclass=QueuePool,
            pool_size=1,
            max_overflow=0,
        )
        monkeypatch.setattr(
            "keep.api.bl.enrichments_bl.get_session_sync",
            lambda: SQLModelSession(engine),
        )

        bl = EnrichmentsBl(tenant_id="test_tenant")
        # Session(engine) alone doesn't check out a connection - mirror
        # production, where a query (e.g. the refresh() in _enrich_entity)
        # is what actually acquires one and leaves a transaction open.
        bl.db_session.execute(text("SELECT 1"))
        assert bl.db_session.in_transaction()
        assert engine.pool.checkedout() == 1

        bl.close()
        assert engine.pool.checkedout() == 0

        # pool must be usable again, not exhausted
        with engine.connect():
            pass

    @patch(
        "keep.api.bl.enrichments_bl.ElasticClient",
        side_effect=RuntimeError("bad elastic config"),
    )
    @patch("keep.api.bl.enrichments_bl.get_session_sync")
    def test_closes_session_if_init_fails_after_session_created(
        self, mock_get_session, mock_elastic_cls
    ):
        """
        If anything raises between session creation and __init__
        completing (e.g. ElasticClient on bad config), the constructor
        never returns an instance, so no caller's try/finally can call
        close() on it - the session must be closed by __init__ itself.
        """
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        with pytest.raises(RuntimeError, match="bad elastic config"):
            EnrichmentsBl(tenant_id="test_tenant")

        mock_session.close.assert_called_once()
