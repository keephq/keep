"""
Business logic for handling dismissal expiry.

This module provides functionality to automatically expire alert dismissals
when their dismissedUntil timestamp has passed.
"""

import datetime
import logging
from typing import List, Optional

from sqlmodel import Session, select
from keep.api.core.db import get_session_sync
from keep.api.core.db_utils import get_json_extract_field
from keep.api.core.elastic import ElasticClient  
from keep.api.core.dependencies import get_pusher_client
from keep.api.models.action_type import ActionType
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import Alert, AlertAudit, AlertEnrichment


class DismissalExpiryBl:
    
    @staticmethod
    def get_alerts_with_expired_dismissals(session: Session) -> List[AlertEnrichment]:
        """
        Get all AlertEnrichment records that have expired dismissedUntil timestamps.
        
        Returns enrichment records where:
        1. dismissed = true  
        2. dismissedUntil is not null and not "forever"
        3. dismissedUntil timestamp is in the past
        
        Args:
            session: Database session
            
        Returns:
            List of AlertEnrichment objects with expired dismissals
        """
        logger = logging.getLogger(__name__)
        now = datetime.datetime.now(datetime.timezone.utc)
        
        logger.info("Searching for enrichments with expired dismissals")
        
        # Query for enrichments with dismissed=true and dismissedUntil set
        # Use the proper helper function for cross-database compatibility
        dismissed_field = get_json_extract_field(session, AlertEnrichment.enrichments, "dismissed")
        dismissed_until_field = get_json_extract_field(session, AlertEnrichment.enrichments, "dismissUntil")
        
        # Build cross-database compatible boolean comparison
        # Different databases store/extract JSON booleans differently:
        # - SQLite: json_extract can return 1/0 for true/false OR "True"/"False"/"true"/"false" strings depending on how data was stored
        # - MySQL: JSON_UNQUOTE(JSON_EXTRACT()) returns "true"/"false" strings (lowercase)
        # - PostgreSQL: json_extract_path_text() returns "true"/"false" strings (lowercase) OR "True"/"False" (depending on input)
        if session.bind.dialect.name == "sqlite":
            # Handle both integer and string representations in SQLite
            dismissed_condition = (dismissed_field == 1) | (dismissed_field == "True") | (dismissed_field == "true")
        elif session.bind.dialect.name == "postgresql":
            # PostgreSQL can return both "true"/"false" and "True"/"False" depending on how the data was stored
            dismissed_condition = (dismissed_field == "true") | (dismissed_field == "True")
        else:
            # For MySQL, compare with lowercase string "true"
            dismissed_condition = dismissed_field == "true"
        
        query = session.exec(
            select(AlertEnrichment).where(
                dismissed_condition,
                # dismissedUntil is not null
                dismissed_until_field.isnot(None),
                # dismissedUntil is not "forever"
                dismissed_until_field != "forever",
            )
        )
        
        candidate_enrichments = query.all()
        
        logger.info(f"Found {len(candidate_enrichments)} candidate enrichments with dismissals")
        
        # Filter in Python for safety and clarity (parsing ISO timestamps)
        expired_enrichments = []
        for enrichment in candidate_enrichments:
            dismiss_until_str = enrichment.enrichments.get("dismissUntil")
            if not dismiss_until_str or dismiss_until_str == "forever":
                continue
                
            try:
                # Parse the dismissedUntil timestamp  
                dismiss_until = datetime.datetime.strptime(
                    dismiss_until_str, "%Y-%m-%dT%H:%M:%S.%fZ"
                ).replace(tzinfo=datetime.timezone.utc)
                
                # Check if it's expired (current time > dismissedUntil)
                if now > dismiss_until:
                    logger.info(
                        f"Found expired dismissal for fingerprint {enrichment.alert_fingerprint}",
                        extra={
                            "tenant_id": enrichment.tenant_id,
                            "fingerprint": enrichment.alert_fingerprint,
                            "dismissed_until": dismiss_until_str,
                            "expired_by_seconds": (now - dismiss_until).total_seconds()
                        }
                    )
                    expired_enrichments.append(enrichment)
                    
            except (ValueError, TypeError) as e:
                # Log invalid timestamp but don't fail
                logger.warning(
                    f"Invalid dismissedUntil timestamp for fingerprint {enrichment.alert_fingerprint}: {dismiss_until_str}",
                    extra={
                        "tenant_id": enrichment.tenant_id, 
                        "fingerprint": enrichment.alert_fingerprint,
                        "error": str(e)
                    }
                )
                continue
        
        logger.info(f"Found {len(expired_enrichments)} enrichments with expired dismissals")
        return expired_enrichments
    
    @staticmethod
    def check_dismissal_expiry(logger: logging.Logger, session: Optional[Session] = None):
        """
        Check for alerts with expired dismissedUntil and restore them.
        
        This function:
        1. Finds AlertEnrichment records with expired dismissedUntil timestamps
        2. Updates their enrichments to set dismissed=false and dismissedUntil=null
        3. Cleans up disposable fields  
        4. Updates Elasticsearch indexes
        5. Notifies UI of changes
        6. Adds audit trail
        
        Args:
            logger: Logger instance for detailed logging
            session: Optional database session (creates new if None)
        """
        logger.info("Starting dismissal expiry check")
        
        local_session = False
        if session is None:
            session = get_session_sync()
            local_session = True
            
        try:
            # Find enrichments with expired dismissedUntil
            expired_enrichments = DismissalExpiryBl.get_alerts_with_expired_dismissals(session)
            
            if not expired_enrichments:
                logger.info("No enrichments with expired dismissals found")
                return
                
            logger.info(f"Processing {len(expired_enrichments)} expired dismissal enrichments")
            
            # Process each expired enrichment
            for enrichment in expired_enrichments:
                logger.info(
                    f"Processing expired dismissal for fingerprint {enrichment.alert_fingerprint}",
                    extra={
                        "tenant_id": enrichment.tenant_id,
                        "fingerprint": enrichment.alert_fingerprint,
                        "dismissed_until": enrichment.enrichments.get("dismissedUntil")
                    }
                )
                
                # Store original values for audit
                original_dismissed = enrichment.enrichments.get("dismissed", False)
                original_dismissed_until = enrichment.enrichments.get("dismissedUntil")
                
                # Update enrichment - set back to not dismissed
                new_enrichments = enrichment.enrichments.copy()
                new_enrichments["dismissed"] = False
                new_enrichments["dismissUntil"] = None  # Clear the original field
                
                # Reset status if it was set to suppressed during dismissal
                enrichment_status = enrichment.enrichments.get("status")
                if enrichment_status == "suppressed":
                    # Remove the suppressed status entirely - let the system use the original alert status
                    # The AlertDto will get the status from the original alert event data
                    new_enrichments.pop("status", None)
                    logger.info(
                        f"Removed suppressed status for fingerprint {enrichment.alert_fingerprint} - will use original alert status",
                        extra={
                            "tenant_id": enrichment.tenant_id,
                            "fingerprint": enrichment.alert_fingerprint,
                            "removed_status": enrichment_status
                        }
                    )
                
                # Clean up ALL disposable fields (use pattern matching instead of hardcoded list)
                cleaned_fields = []
                keys_to_remove = []
                for field_name in new_enrichments.keys():
                    if field_name.startswith("disposable_"):
                        keys_to_remove.append(field_name)
                        cleaned_fields.append(field_name)
                
                # Remove the disposable fields
                for field_name in keys_to_remove:
                    new_enrichments.pop(field_name)
                        
                if cleaned_fields:
                    logger.info(
                        f"Cleaned up disposable fields: {cleaned_fields}",
                        extra={
                            "tenant_id": enrichment.tenant_id,
                            "fingerprint": enrichment.alert_fingerprint
                        }
                    )
                
                # Update the enrichment record
                enrichment.enrichments = new_enrichments
                session.add(enrichment)
                
                # Add audit trail
                try:
                    audit = AlertAudit(
                        tenant_id=enrichment.tenant_id,
                        fingerprint=enrichment.alert_fingerprint,
                        user_id="system",
                        action=ActionType.DISMISSAL_EXPIRED.value,  # Use .value to get the string
                        description=(
                            f"Dismissal expired at {original_dismissed_until}, "
                            f"enrichment updated from dismissed={original_dismissed} to dismissed=False"
                        )
                    )
                    session.add(audit)
                    logger.info(
                        "Added audit trail for expired dismissal",
                        extra={
                            "tenant_id": enrichment.tenant_id,
                            "fingerprint": enrichment.alert_fingerprint
                        }
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to add audit trail for fingerprint {enrichment.alert_fingerprint}: {e}",
                        extra={
                            "tenant_id": enrichment.tenant_id,
                            "fingerprint": enrichment.alert_fingerprint
                        }
                    )
                
                # Update Elasticsearch index
                try:
                    # Get the latest alert for this fingerprint to create AlertDto
                    latest_alert = session.exec(
                        select(Alert)
                        .where(Alert.tenant_id == enrichment.tenant_id)
                        .where(Alert.fingerprint == enrichment.alert_fingerprint)
                        .order_by(Alert.timestamp.desc())
                        .limit(1)
                    ).first()
                    
                    if latest_alert:
                        # Create AlertDto with updated enrichments
                        alert_data = latest_alert.event.copy()
                        
                        # Only update specific enrichment fields, don't override alert event data with None values
                        enrichment_fields = ['dismissed', 'dismissUntil', 'note', 'assignee', 'status']
                        for field in enrichment_fields:
                            if field in new_enrichments and new_enrichments[field] is not None:
                                alert_data[field] = new_enrichments[field]
                            elif field in new_enrichments and new_enrichments[field] is None and field in ['dismissed', 'dismissUntil']:
                                # For dismissal fields, None is a valid value (means not dismissed)
                                alert_data[field] = new_enrichments[field]
                        
                        alert_dto = AlertDto(**alert_data)
                        
                        elastic_client = ElasticClient(enrichment.tenant_id)
                        elastic_client.index_alert(alert_dto)
                        logger.info(
                            f"Updated Elasticsearch index for fingerprint {enrichment.alert_fingerprint}",
                            extra={
                                "tenant_id": enrichment.tenant_id,
                                "fingerprint": enrichment.alert_fingerprint
                            }
                        )
                    else:
                        logger.warning(
                            f"No alert found for fingerprint {enrichment.alert_fingerprint}, skipping Elasticsearch update",
                            extra={
                                "tenant_id": enrichment.tenant_id,
                                "fingerprint": enrichment.alert_fingerprint
                            }
                        )
                        
                except Exception as e:
                    logger.error(
                        f"Failed to update Elasticsearch for fingerprint {enrichment.alert_fingerprint}: {e}",
                        extra={
                            "tenant_id": enrichment.tenant_id,
                            "fingerprint": enrichment.alert_fingerprint
                        }
                    )
                
                # Notify UI of change
                try:
                    pusher_client = get_pusher_client()
                    if pusher_client:
                        pusher_client.trigger(
                            f"private-{enrichment.tenant_id}",
                            "alert-update",
                            {
                                "fingerprint": enrichment.alert_fingerprint, 
                                "action": "dismissal_expired"
                            }
                        )
                        logger.info(
                            f"Sent UI notification for fingerprint {enrichment.alert_fingerprint}",
                            extra={
                                "tenant_id": enrichment.tenant_id,
                                "fingerprint": enrichment.alert_fingerprint
                            }
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to send UI notification for fingerprint {enrichment.alert_fingerprint}: {e}",
                        extra={
                            "tenant_id": enrichment.tenant_id,
                            "fingerprint": enrichment.alert_fingerprint
                        }
                    )
            
            # Commit all changes
            session.commit()
            logger.info(
                f"Successfully processed {len(expired_enrichments)} expired dismissal enrichments",
                extra={"processed_count": len(expired_enrichments)}
            )
            
        except Exception as e:
            logger.error(f"Error during dismissal expiry check: {e}", exc_info=True)
            session.rollback()
            raise
        finally:
            if local_session:
                session.close()
            logger.info("Dismissal expiry check completed")
