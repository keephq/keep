from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from keep.api.core.db import get_session
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.api.models.db.anomaly_result import AnomalyResult
from keep.api.models.time_stamp import TimeStampFilter

router = APIRouter()


@router.get("/anomaly/results", description="Get anomaly detection results")
def get_anomaly_results(
        authenticated_entity: AuthenticatedEntity = Depends(
            IdentityManagerFactory.get_auth_verifier(["read:alert"])
        ),
        session: Session = Depends(get_session),
        fingerprint: Optional[str] = Query(None),
        is_anomaly: Optional[bool] = Query(None),
        limit: int = Query(100, le=1000),
        offset: int = Query(0, ge=0),
        time_filter: TimeStampFilter = Depends(),
) -> dict:
    """Get anomaly detection results with filtering."""
    tenant_id = authenticated_entity.tenant_id

    query = select(AnomalyResult).where(AnomalyResult.tenant_id == tenant_id)

    if fingerprint:
        query = query.where(AnomalyResult.alert_fingerprint == fingerprint)
    if is_anomaly is not None:
        query = query.where(AnomalyResult.is_anomaly == is_anomaly)

        # Apply time filter
    if time_filter.start_time:
        query = query.where(AnomalyResult.timestamp >= time_filter.start_time)
    if time_filter.end_time:
        query = query.where(AnomalyResult.timestamp <= time_filter.end_time)

        # Get total count
    total_count = len(session.exec(query).all())

    # Apply pagination
    query = query.order_by(AnomalyResult.timestamp.desc()).offset(offset).limit(limit)
    results = session.exec(query).all()

    return {
        "results": results,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.post("/anomaly/{fingerprint}/dismiss", description="Dismiss alert as false positive")
def dismiss_alert_as_false_positive(
        fingerprint: str,
        authenticated_entity: AuthenticatedEntity = Depends(
            IdentityManagerFactory.get_auth_verifier(["write:alert"])
        ),
        session: Session = Depends(get_session),
):
    """Mark an alert as dismissed false positive."""
    tenant_id = authenticated_entity.tenant_id

    # Update the alert status
    from keep.api.models.db.alert import Alert
    from keep.api.models.alert import AlertStatus

    alert = session.exec(
        select(Alert).where(
            Alert.tenant_id == tenant_id,
            Alert.fingerprint == fingerprint
        )
    ).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = AlertStatus.DISMISSED
    alert.dismissed = True
    alert.dismissed_until = None
    session.commit()

    return {"status": "dismissed", "fingerprint": fingerprint}