#!/usr/bin/env python3
"""
Update severity and status for Mailgun alerts that were processed without
the intelligent extraction logic.

This script identifies Mailgun alerts with default severity/status values
and updates them using the new intelligent extraction methods.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keep.api.core.db import get_session_sync
from keep.api.models.db.alert import Alert
from keep.providers.mailgun_provider.mailgun_provider import MailgunProvider
from sqlalchemy import and_, or_
from datetime import datetime, timedelta


def update_mailgun_alerts(tenant_id: str, dry_run: bool = True, days_back: int = 30):
    """
    Update severity and status for Mailgun alerts.
    
    Args:
        tenant_id: Tenant ID to update alerts for
        dry_run: If True, only show what would be updated
        days_back: How many days back to check (default: 30)
    """
    session = get_session_sync()
    
    try:
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        print(f"Searching for Mailgun alerts from the last {days_back} days...")
        print(f"Tenant ID: {tenant_id}")
        print(f"Cutoff date: {cutoff_date}")
        print()
        
        # Get Mailgun alerts that likely need updating
        # Focus on alerts with default severity="info" which might be wrong
        alerts = session.query(Alert).filter(
            and_(
                Alert.tenant_id == tenant_id,
                Alert.provider_type == "mailgun",
                Alert.timestamp >= cutoff_date,
            )
        ).all()
        
        print(f"Found {len(alerts)} total Mailgun alerts")
        print()
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        # Group by severity for reporting
        severity_changes = {}
        status_changes = {}
        
        for alert in alerts:
            try:
                # Get current values
                event = alert.event
                current_severity = event.get("severity", "info")
                current_status = event.get("status", "firing")
                alert_name = event.get("name", "Unknown")[:80]
                
                # Build pseudo-event for extraction
                email_type = event.get("email_type", "alert")
                
                # If no email_type, try to classify from available data
                if not email_type or email_type == "alert":
                    # Get source (email sender)
                    source_list = event.get("source", [])
                    email_from = source_list[0] if isinstance(source_list, list) and len(source_list) > 0 else ""
                    
                    pseudo_event = {
                        "from": email_from,
                        "subject": event.get("name", ""),
                        "stripped-text": event.get("message", ""),
                        "Body-plain": event.get("description", ""),
                        "Content-Type": event.get("Content-Type", ""),
                    }
                    email_type = MailgunProvider._classify_email_type(pseudo_event)
                
                # Extract severity and status using new logic
                extraction_event = {
                    "subject": event.get("name", ""),
                    "stripped-text": event.get("message", ""),
                    "Body-plain": event.get("description", ""),
                }
                
                new_severity = MailgunProvider._extract_severity_from_email(
                    extraction_event, 
                    email_type
                )
                new_status = MailgunProvider._extract_status_from_email(
                    extraction_event
                )
                
                # Check if update is needed
                needs_update = (
                    current_severity != new_severity or 
                    current_status != new_status or
                    not event.get("email_type")
                )
                
                if needs_update:
                    print(f"Alert: {alert_name}")
                    
                    if current_severity != new_severity:
                        print(f"  Severity: {current_severity} → {new_severity}")
                        severity_changes[f"{current_severity}→{new_severity}"] = \
                            severity_changes.get(f"{current_severity}→{new_severity}", 0) + 1
                    
                    if current_status != new_status:
                        print(f"  Status: {current_status} → {new_status}")
                        status_changes[f"{current_status}→{new_status}"] = \
                            status_changes.get(f"{current_status}→{new_status}", 0) + 1
                    
                    if not event.get("email_type"):
                        print(f"  Email Type: (none) → {email_type}")
                    
                    print(f"  Timestamp: {alert.timestamp}")
                    print()
                    
                    if not dry_run:
                        # Update the event dict
                        event["severity"] = new_severity
                        event["status"] = new_status
                        if not event.get("email_type"):
                            event["email_type"] = email_type
                        
                        # Update in database
                        alert.event = event
                        session.add(alert)
                        updated_count += 1
                else:
                    skipped_count += 1
            
            except Exception as e:
                print(f"❌ Error processing alert {alert.id}: {e}")
                error_count += 1
                continue
        
        # Commit if not dry run
        if not dry_run and updated_count > 0:
            session.commit()
            print(f"\n✅ Successfully updated {updated_count} alerts")
        elif dry_run and updated_count > 0:
            print(f"\n📋 DRY RUN: Would update {updated_count} alerts")
            print("Run with --apply to actually update the database")
        else:
            print(f"\n✅ No alerts need updating")
        
        # Print summary
        print(f"\nSummary:")
        print(f"  Total alerts checked: {len(alerts)}")
        print(f"  Need updating: {updated_count}")
        print(f"  Already correct: {skipped_count}")
        print(f"  Errors: {error_count}")
        
        if severity_changes:
            print(f"\nSeverity changes:")
            for change, count in severity_changes.items():
                print(f"  {change}: {count} alerts")
        
        if status_changes:
            print(f"\nStatus changes:")
            for change, count in status_changes.items():
                print(f"  {change}: {count} alerts")
    
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Update severity and status for Mailgun alerts"
    )
    parser.add_argument(
        "--tenant-id", 
        default="keep",
        help="Tenant ID (default: keep)"
    )
    parser.add_argument(
        "--apply", 
        action="store_true", 
        help="Actually update the database (default is dry-run)"
    )
    parser.add_argument(
        "--days", 
        type=int,
        default=30,
        help="How many days back to check (default: 30)"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Mailgun Alert Metadata Update Script")
    print("=" * 70)
    print()
    
    if args.apply:
        print("⚠️  APPLY MODE: Will update the database")
    else:
        print("📋 DRY RUN MODE: Will only show what would change")
    
    print()
    
    update_mailgun_alerts(
        tenant_id=args.tenant_id,
        dry_run=not args.apply,
        days_back=args.days
    )

