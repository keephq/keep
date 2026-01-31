"""
Business logic for handling dismissal expiry.

Automatically expires alert dismissals when their dismissUntil timestamp has passed.

Key guarantees:
- Tenant isolation (no cross-tenant corruption)
- Consistent enrichment field naming (dismissUntil)
- Robust timestamp parsing
- DB is source of truth; external systems updated AFTER commit
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from keep.api.core.db import get_session_sync
from keep.api.core.db_utils import get_json_extract_field
from keep.api.core.elastic import ElasticClient
from keep.api.core.dependencies import get_pusher_client
from keep.api.models.action_type import ActionType
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import Alert, AlertAudit, AlertEnrichment


CANON_DISMISS_UNTIL = "dismissUntil"
LEGACY_DISMISS_UNTIL = "dismissedUntil"  # tolerate legacy typo if it exists
DISMISSED_FIELD = "dismissed"


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_iso_ts(value: str) -> Optional[dt.datetime]:
    """
    Parse common ISO/RFC3339 timestamp strings into an aware UTC datetime.
    Accepts:
      - 2024-01-31T12:00:00Z
      - 2024-01-31T12:00:00.000Z
      - 2024-01-31T12:00:00+00:00
      - 2024-01-31T12:00:00.000+00:00
    """
    if not value or not isinstance(value, str):
        return None

    s = value.strip()
    if not s or s == "forever":
        return None

    # Convert trailing Z to +00:00 so fromisoformat works
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    try:
        parsed = dt.datetime.fromisoformat(s)
    except ValueError:
        return None

    # Ensure timezone-aware
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)

    return parsed.astimezone(dt.timezone.utc)


def _get_dismiss_until(enrichments: Dict[str, Any]) -> Optional[str]:
    """
    Return dismissUntil from canonical field, or fall back to legacy field.
    """
    if CANON_DISMISS_UNTIL in enrichments:
        return enrichments.get(CANON_DISMISS_UNTIL)
    return enrichments.get(LEGACY_DISMISS_UNTIL)


def _set_dismiss_until(enrichments: Dict[str, Any], value: Any) -> None:
    """
    Set canonical dismissUntil, and remove legacy field if present.
    """
    enrichments[CANON_DISMISS_UNTIL] = value
    enrichments.pop(LEGACY_DISMISS_UNTIL, None)


def _is_truthy_dismissed(value: Any) -> bool:
    """
    Normalize dismissed field, which may be bool/int/str depending on storage.
    """
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return False


class DismissalExpiryBl:
    @staticmethod
    def get_alerts_with_expired_dismissals(
        session: Session,
        tenant_id: str,
        limit: int = 500,
    ) -> List[AlertEnrichment]:
        """
        Fetch candidate enrichments for a single tenant, then filter in Python.

        We keep SQL filtering minimal because JSON extraction types vary across DBs.
        """
        logger = logging.getLogger(__name__)
        now = _utcnow()

        dismissed_field = get_json_extract_field(session, AlertEnrichment.enrichments, DISMISSED_FIELD)
        dismiss_until_field = get_json_extract_field(session, AlertEnrichment.enrichments, CANON_DISMISS_UNTIL)

        # Candidate query:
        # - tenant scoped
        # - dismissed exists in JSON (we'll truth-test in Python)
        # - dismissUntil exists (we'll parse/expire check in Python)
        rows = session.exec(
            select(AlertEnrichment)
            .where(AlertEnrichment.tenant_id == tenant_id)
            .where(dismissed_field.isnot(None))
            .where(dismiss_until_field.isnot(None))
            .limit(limit)
        ).all()

        expired: List[AlertEnrichment] = []

        for enr in rows:
            dismissed_val = enr.enrichments.get(DISMISSED_FIELD)
            if not _is_truthy_dismissed(dismissed_val):
                continue

            until_str = _get_dismiss_until(enr.enrichments)
            until_dt = _parse_iso_ts(until_str) if isinstance(until_str, str) else None
            if not until_dt:
                # ignore forever/invalid/empty
                continue

            if now > until_dt:
                expired.append(enr)

        logger.info(
            "Dismissal expiry candidates=%s expired=%s tenant_id=%s",
            len(rows),
            len(expired),
            tenant_id,
        )
        return expired

    @staticmethod
    def check_dismissal_expiry(
        logger: logging.Logger,
        tenant_id: str,
        session: Optional[Session] = None,
        batch_limit: int = 500,
    ) -> int:
        """
        Expire dismissals for a single tenant.

        Returns number of enrichments successfully updated in DB.
        """
        owned_session = session is None
        if owned_session:
            session = get_session_sync()

        assert session is not None
        updated_count = 0

        try:
            expired = DismissalExpiryBl.get_alerts_with_expired_dismissals(
                session=session,
                tenant_id=tenant_id,
                limit=batch_limit,
            )

            if not expired:
                logger.info("No expired dismissals found tenant_id=%s", tenant_id)
                return 0

            # Process each enrichment independently:
            # - commit DB first
            # - then external side effects (elastic/pusher)
            for enr in expired:
                fp = enr.alert_fingerprint
                try:
                    original = dict(enr.enrichments or {})
                    original_dismissed = original.get(DISMISSED_FIELD, False)
                    original_until = _get_dismiss_until(original)

                    new_enr = dict(original)
                    new_enr[DISMISSED_FIELD] = False
                    _set_dismiss_until(new_enr, None)

                    # If you truly only want to clear suppressed, document it.
                    if new_enr.get("status") == "suppressed":
                        new_enr.pop("status", None)

                    # Remove disposable_* keys
                    for k in list(new_enr.keys()):
                        if isinstance(k, str) and k.startswith("disposable_"):
                            new_enr.pop(k, None)

                    enr.enrichments = new_enr
                    session.add(enr)

                    # Audit trail (if enum missing, fail loudly here so you notice)
                    audit = AlertAudit(
                        tenant_id=enr.tenant_id,
                        fingerprint=fp,
                        user_id="system",
                        action=ActionType.DISMISSAL_EXPIRED.value,
                        description=(
                            f"Dismissal expired at {original_until}; "
                            f"dismissed {original_dismissed} -> False"
                        ),
                    )
                    session.add(audit)

                    session.commit()
                    updated_count += 1

                except Exception as e:
                    session.rollback()
                    logger.error(
                        "Failed DB update for expired dismissal tenant_id=%s fingerprint=%s err=%s",
                        enr.tenant_id,
                        fp,
                        str(e),
                        exc_info=True,
                    )
                    continue

                # Side effects AFTER commit
                DismissalExpiryBl._post_commit_side_effects(logger, session, enr)

            logger.info(
                "Dismissal expiry completed tenant_id=%s updated=%s",
                tenant_id,
                updated_count,
            )
            return updated_count

        finally:
            if owned_session:
                try:
                    session.close()
                except Exception:
                    logger.exception("Failed closing owned session")

    @staticmethod
    def _post_commit_side_effects(logger: logging.Logger, session: Session, enrichment: AlertEnrichment) -> None:
        """
        Best-effort external updates. DB already committed.
        Failures here should be logged and retried out-of-band if needed.
        """
        fp = enrichment.alert_fingerprint
        tenant_id = enrichment.tenant_id

        # Update Elasticsearch
        try:
            latest_alert = session.exec(
                select(Alert)
                .where(Alert.tenant_id == tenant_id)
                .where(Alert.fingerprint == fp)
                .order_by(Alert.timestamp.desc())
                .limit(1)
            ).first()

            if latest_alert and isinstance(latest_alert.event, dict):
                alert_data = dict(latest_alert.event)

                # Patch only enrichment-relevant fields
                enr = enrichment.enrichments or {}
                for field in ("dismissed", "dismissUntil", "note", "assignee", "status"):
                    if field == "dismissUntil":
                        # ensure canonical naming in indexed doc
                        alert_data[field] = enr.get(CANON_DISMISS_UNTIL)
                    else:
                        if field in enr:
                            alert_data[field] = enr.get(field)

                alert_dto = AlertDto(**alert_data)
                ElasticClient(tenant_id).index_alert(alert_dto)
            else:
                logger.warning(
                    "No latest alert event found for ES update tenant_id=%s fingerprint=%s",
                    tenant_id,
                    fp,
                )
        except Exception as e:
            logger.error(
                "Elasticsearch update failed tenant_id=%s fingerprint=%s err=%s",
                tenant_id,
                fp,
                str(e),
                exc_info=True,
            )

        # Notify UI
        try:
            pusher = get_pusher_client()
            if pusher:
                pusher.trigger(
                    f"private-{tenant_id}",
                    "alert-update",
                    {"fingerprint": fp, "action": "dismissal_expired"},
                )
        except Exception as e:
            logger.error(
                "Pusher notify failed tenant_id=%s fingerprint=%s err=%s",
                tenant_id,
                fp,
                str(e),
                exc_info=True,
            )