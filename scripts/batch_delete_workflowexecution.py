from dotenv import find_dotenv, load_dotenv
from sqlalchemy import func
from sqlmodel import Session
import logging
import time
from datetime import datetime, timedelta
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from typing import List, Optional, Dict, Any, Tuple

from keep.api.core.db_utils import create_db_engine
from keep.api.models.db.workflow import WorkflowExecution, WorkflowExecutionLog, WorkflowToAlertExecution, WorkflowToIncidentExecution

load_dotenv(find_dotenv())


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_db_connection():
    """Create database engine and session factory with appropriate connection pooling."""
    engine = create_db_engine()
    SQLAlchemyInstrumentor().instrument(enable_commenter=True, engine=engine)
    with Session(engine) as session:
        return engine, session


def batch_delete_workflow_executions(
    session: Session,
    criteria: Dict[str, Any],
    batch_size: int = 1000,
    dry_run: bool = False,
    age_days: Optional[int] = None,
    status_filter: Optional[List[str]] = None,
    total_limit: Optional[int] = None,
) -> Tuple[int, int, int, int]:
    """
    Efficiently delete workflow executions and related records in batches.
    
    Args:
        session_factory: SQLAlchemy session factory
        criteria: Dictionary of filter criteria for targeting specific executions
        batch_size: Number of records to delete in each batch
        dry_run: If True, only count but don't delete
        age_days: If provided, only delete executions older than this many days
        status_filter: If provided, only delete executions with these statuses
        total_limit: Optional limit on total number of records to process
        
    Returns:
        Tuple containing counts of deleted (executions, logs, alert_executions, incident_executions)
    """
    start_time = time.time()
    
    # Initialize counters
    total_executions_deleted = 0
    total_logs_deleted = 0
    total_alert_executions_deleted = 0
    total_incident_executions_deleted = 0
    
    # Set up age filter if provided
    if age_days:
        cutoff_date = datetime.utcnow() - timedelta(days=age_days)
        logger.info(f"Filtering executions older than {cutoff_date}")
    else:
        cutoff_date = None
    
    with session as count_session:
        # Build base query for counting
        base_query = count_session.query(WorkflowExecution)
        
        # Apply cutoff date filter if provided
        if cutoff_date:
            base_query = base_query.filter(WorkflowExecution.started < cutoff_date)
            
        # Apply status filter if provided
        if status_filter:
            base_query = base_query.filter(WorkflowExecution.status.in_(status_filter))
            
        # Apply any other criteria
        for key, value in criteria.items():
            if hasattr(WorkflowExecution, key):
                base_query = base_query.filter(getattr(WorkflowExecution, key) == value)
        
        # Get total count for progress reporting
        total_count = base_query.count()
        
        if total_limit and total_limit < total_count:
            total_count = total_limit
            logger.info(f"Limiting deletion to {total_limit} records (out of {total_count} matching records)")
        
        logger.info(f"Found {total_count} workflow executions matching deletion criteria")
        
        if dry_run:
            logger.info("DRY RUN MODE: No records will be deleted")
    
    # Only proceed if there are records to delete
    if total_count == 0:
        logger.info("No records to delete. Exiting.")
        return 0, 0, 0, 0
    
    # Process in batches
    processed_count = 0
    batch_count = 0
    
    # Initialize for first batch
    last_id = ""
    has_more = True
    
    # While we have more records to process and haven't hit our limit
    while has_more and (total_limit is None or processed_count < total_limit):
        # Start a new session for each batch
        with session as session:
            try:
                # Create query for current batch
                query = session.query(WorkflowExecution)
                
                # Apply the same filters as for counting
                if cutoff_date:
                    query = query.filter(WorkflowExecution.started < cutoff_date)
                    
                if status_filter:
                    query = query.filter(WorkflowExecution.status.in_(status_filter))
                    
                for key, value in criteria.items():
                    if hasattr(WorkflowExecution, key):
                        query = query.filter(getattr(WorkflowExecution, key) == value)
                
                # For pagination - grab IDs greater than the last one we processed
                if last_id:
                    query = query.filter(WorkflowExecution.id > last_id)
                
                # Order by ID for consistent pagination
                query = query.order_by(WorkflowExecution.id)
                
                # Apply batch size limit
                query = query.limit(batch_size)
                
                # First, get all execution IDs for this batch
                execution_batch = query.all()
                
                # Check if we have more data to process
                if not execution_batch:
                    has_more = False
                    break
                
                # Get IDs for the current batch
                execution_ids = [exe.id for exe in execution_batch]
                last_id = execution_ids[-1]  # Save the last ID for next batch
                
                # Batch size may be smaller than requested if we're at the end
                actual_batch_size = len(execution_ids)
                
                # For reporting, count related records
                logs_count = session.query(func.count(WorkflowExecutionLog.id)).filter(
                    WorkflowExecutionLog.workflow_execution_id.in_(execution_ids)
                ).scalar()
                
                alert_executions_count = session.query(func.count(WorkflowToAlertExecution.id)).filter(
                    WorkflowToAlertExecution.workflow_execution_id.in_(execution_ids)
                ).scalar()
                
                incident_executions_count = session.query(func.count(WorkflowToIncidentExecution.id)).filter(
                    WorkflowToIncidentExecution.workflow_execution_id.in_(execution_ids)
                ).scalar()
                
                if not dry_run:
                    # Delete in optimal order - start with related tables
                    # Note: With proper foreign keys and CASCADE, we could just delete WorkflowExecution
                    # But let's be explicit for safety and reporting
                    
                    # 1. Delete workflow execution logs
                    session.query(WorkflowExecutionLog).filter(
                        WorkflowExecutionLog.workflow_execution_id.in_(execution_ids)
                    ).delete(synchronize_session=False)
                    
                    # 2. Delete workflow to alert executions
                    session.query(WorkflowToAlertExecution).filter(
                        WorkflowToAlertExecution.workflow_execution_id.in_(execution_ids)
                    ).delete(synchronize_session=False)
                    
                    # 3. Delete workflow to incident executions
                    session.query(WorkflowToIncidentExecution).filter(
                        WorkflowToIncidentExecution.workflow_execution_id.in_(execution_ids)
                    ).delete(synchronize_session=False)
                    
                    # 4. Finally delete the workflow executions themselves
                    session.query(WorkflowExecution).filter(
                        WorkflowExecution.id.in_(execution_ids)
                    ).delete(synchronize_session=False)
                    
                    # Commit the transaction
                    session.commit()
                
                # Update counters
                total_executions_deleted += actual_batch_size
                total_logs_deleted += logs_count
                total_alert_executions_deleted += alert_executions_count
                total_incident_executions_deleted += incident_executions_count
                
                # Update processed count for progress reporting
                processed_count += actual_batch_size
                batch_count += 1
                
                # Log progress
                elapsed = time.time() - start_time
                rate = processed_count / elapsed if elapsed > 0 else 0
                pct_complete = (processed_count / total_count) * 100 if total_count > 0 else 0
                
                logger.info(
                    f"Batch {batch_count}: Processed {processed_count}/{total_count} executions "
                    f"({pct_complete:.2f}%) at {rate:.2f} records/sec. "
                    f"Batch contained {actual_batch_size} executions, {logs_count} logs, "
                    f"{alert_executions_count} alert links, {incident_executions_count} incident links"
                )
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error processing batch {batch_count}: {e}")
                # Continue with next batch rather than failing completely
    
    # Final stats
    elapsed = time.time() - start_time
    rate = processed_count / elapsed if elapsed > 0 else 0
    
    action = "Would delete" if dry_run else "Deleted"
    logger.info(
        f"Completed! {action} {total_executions_deleted} workflow executions, "
        f"{total_logs_deleted} logs, {total_alert_executions_deleted} alert links, "
        f"{total_incident_executions_deleted} incident links "
        f"in {elapsed:.2f} seconds ({rate:.2f} executions/sec)"
    )
    
    return (
        total_executions_deleted,
        total_logs_deleted,
        total_alert_executions_deleted,
        total_incident_executions_deleted
    )


def cleanup_old_workflow_executions(
    retention_days: int = 30,
    batch_size: int = 1000,
    dry_run: bool = False
):
    """
    Cleanup function to delete workflow executions older than specified retention period.
    
    Args:
        retention_days: Number of days to retain workflow executions
        batch_size: Size of batches for deletion
        dry_run: If True, only simulate deletion
    """
    engine, Session = get_db_connection()
    
    logger.info(f"Starting cleanup of workflow executions older than {retention_days} days")
    
    # Delete completed executions
    logger.info("Processing completed executions...")
    completed_count = batch_delete_workflow_executions(
        session=Session,
        criteria={},
        batch_size=batch_size,
        dry_run=dry_run,
        age_days=retention_days,
        status_filter=["complete", "success", "completed"],  # Adjust status names as needed
    )
    
    # Delete failed executions (might want different retention policy)
    logger.info("Processing failed executions...")
    failed_count = batch_delete_workflow_executions(
        session=Session,
        criteria={},
        batch_size=batch_size,
        dry_run=dry_run,
        age_days=retention_days,  # Could use a different retention for failed ones
        status_filter=["failed", "error"],  # Adjust status names as needed
    )
    
    logger.info("Cleanup complete!")
    return {
        "completed": completed_count,
        "failed": failed_count
    }


# Example of how to use the deletion function
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Delete workflow execution logs in batches")
    parser.add_argument("--retention-days", type=int, default=30, help="Retention period in days")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for deletion")
    parser.add_argument("--dry-run", action="store_true", help="Simulate deletion without actually deleting")
    parser.add_argument("--workflow-id", help="Limit deletion to a specific workflow ID")
    
    args = parser.parse_args()
    
    if args.workflow_id:
        # Delete executions for a specific workflow
        engine, session = get_db_connection()
        batch_delete_workflow_executions(
            session=session,
            criteria={"workflow_id": args.workflow_id},
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            age_days=args.retention_days
        )
    else:
        # Run the general cleanup
        cleanup_old_workflow_executions(
            retention_days=args.retention_days,
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )