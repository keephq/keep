from dotenv import find_dotenv, load_dotenv
from sqlalchemy import func, select, delete, text
from sqlmodel import Session, select
import logging
import time
from datetime import datetime, timedelta
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from typing import List, Optional, Dict, Any, Tuple
import multiprocessing
import os

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
    session = Session(engine)
    return engine, session


def batch_delete_workflow_executions(
    session: Session,
    criteria: Dict[str, Any],
    batch_size: int = 5000,  # Increased default batch size
    dry_run: bool = False,
    age_days: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    status_filter: Optional[List[str]] = None,
    total_limit: Optional[int] = None,
    skip_count: bool = False,  # Option to skip slow counting for large tables
    estimated_count: Optional[int] = None  # Allow passing estimated count to skip slow counting
) -> Tuple[int, int, int, int]:
    """
    Efficiently delete workflow executions and related records in batches.
    
    Args:
        session_factory: SQLAlchemy session factory
        criteria: Dictionary of filter criteria for targeting specific executions
        batch_size: Number of records to delete in each batch
        dry_run: If True, only count but don't delete
        age_days: If provided, only delete executions older than this many days
        start_time: If provided with end_time, only process executions in this time range
        end_time: If provided with start_time, only process executions in this time range
        status_filter: If provided, only delete executions with these statuses
        total_limit: Optional limit on total number of records to process
        skip_count: Skip the initial count query which can be slow on large tables
        estimated_count: Use this value instead of counting (only if skip_count is True)
        
    Returns:
        Tuple containing counts of deleted (executions, logs, alert_executions, incident_executions)
    """
    start_time_func = time.time()
    
    # Initialize counters
    total_executions_deleted = 0
    total_logs_deleted = 0
    total_alert_executions_deleted = 0
    total_incident_executions_deleted = 0
    
    logger.info(f"criteria: {criteria}, age_days: {age_days}, status_filter: {status_filter}, total_limit: {total_limit}, batch_size: {batch_size}")
    
    # Set up cutoff date if age_days is provided
    cutoff_date = None
    if age_days:
        cutoff_date = datetime.utcnow() - timedelta(days=age_days)
        logger.info(f"Filtering executions older than {cutoff_date}")
    
    # Time range handling (for parallel processing)
    time_range_start = start_time or cutoff_date
    time_range_end = end_time
    
    if time_range_start:
        logger.info(f"Time range start: {time_range_start}")
    if time_range_end:
        logger.info(f"Time range end: {time_range_end}")
    
    total_count = None
    if not skip_count:
        with session as count_session:
            # For very large tables, consider a faster count approximation
            # instead of the full count which can be slow
            try:
                # Build base query for counting
                base_query = select(WorkflowExecution.id)
                
                # Apply time range filters
                if time_range_start:
                    base_query = base_query.where(WorkflowExecution.started >= time_range_start)
                if time_range_end:
                    base_query = base_query.where(WorkflowExecution.started < time_range_end)
                    
                # Apply status filter if provided
                if status_filter:
                    base_query = base_query.where(WorkflowExecution.status.in_(status_filter))
                    
                # Apply any other criteria
                for key, value in criteria.items():
                    if hasattr(WorkflowExecution, key):
                        base_query = base_query.where(getattr(WorkflowExecution, key) == value)
                
                # Get total count for progress reporting - more efficient count
                start_count_time = time.time()
                stmt = select(func.count()).select_from(base_query.subquery())
                total_count = count_session.exec(stmt).first()
                logger.info(f"Count query took {time.time() - start_count_time:.2f} seconds")
                
                if total_count is not None and total_limit is not None and total_limit < total_count:
                    logger.info(f"Limiting deletion to {total_limit} records (out of {total_count} matching records)")
                    total_count = total_limit
                
                logger.info(f"Found {total_count} workflow executions matching deletion criteria")
                
            except Exception as e:
                logger.warning(f"Error during count: {str(e)}. Will proceed without total count.")
                if estimated_count:
                    total_count = estimated_count
                    logger.info(f"Using estimated count: {total_count}")
    elif estimated_count:
        total_count = estimated_count
        logger.info(f"Using provided estimated count: {total_count}")
    
    if dry_run:
        logger.info("DRY RUN MODE: No records will be deleted")
    
    # Process in batches
    processed_count = 0
    batch_count = 0
    
    # Initialize for first batch
    last_id = None
    has_more = True
    
    # While we have more records to process and haven't hit our limit
    while has_more and (total_limit is None or processed_count < total_limit):
        # Start a new session for each batch
        with session as session:
            try:
                batch_start_time = time.time()
                
                # Create query for current batch
                query = select(WorkflowExecution.id)
                
                # Apply time range filters 
                if time_range_start:
                    query = query.where(WorkflowExecution.started >= time_range_start)
                if time_range_end:
                    query = query.where(WorkflowExecution.started < time_range_end)
                    
                if status_filter:
                    query = query.where(WorkflowExecution.status.in_(status_filter))
                    
                for key, value in criteria.items():
                    if hasattr(WorkflowExecution, key):
                        query = query.where(getattr(WorkflowExecution, key) == value)
                
                # For pagination - grab IDs greater than the last one we processed
                if last_id is not None:
                    query = query.where(WorkflowExecution.id > last_id)
                
                # Order by ID for consistent pagination
                query = query.order_by(WorkflowExecution.id)
                
                # Apply batch size limit
                query = query.limit(batch_size)
                
                # First, get all execution IDs for this batch
                execution_ids = session.exec(query).all()
                
                # Check if we have more data to process
                if not execution_ids:
                    has_more = False
                    break
                
                # Save the last ID for next batch
                last_id = execution_ids[-1]
                
                # Batch size may be smaller than requested if we're at the end
                actual_batch_size = len(execution_ids)
                
                # For reporting, count related records
                logs_query = select(func.count()).select_from(WorkflowExecutionLog).where(
                    WorkflowExecutionLog.workflow_execution_id.in_(execution_ids)
                )
                logs_count = session.exec(logs_query).first() or 0
                
                alert_executions_query = select(func.count()).select_from(WorkflowToAlertExecution).where(
                    WorkflowToAlertExecution.workflow_execution_id.in_(execution_ids)
                )
                alert_executions_count = session.exec(alert_executions_query).first() or 0
                
                incident_executions_query = select(func.count()).select_from(WorkflowToIncidentExecution).where(
                    WorkflowToIncidentExecution.workflow_execution_id.in_(execution_ids)
                )
                incident_executions_count = session.exec(incident_executions_query).first() or 0
                
                if not dry_run:
                    # Use bulk operations for faster deletes
                    session.execute(delete(WorkflowExecutionLog).where(
                        WorkflowExecutionLog.workflow_execution_id.in_(execution_ids)
                    ))
                    
                    session.execute(delete(WorkflowToAlertExecution).where(
                        WorkflowToAlertExecution.workflow_execution_id.in_(execution_ids)
                    ))
                    
                    session.execute(delete(WorkflowToIncidentExecution).where(
                        WorkflowToIncidentExecution.workflow_execution_id.in_(execution_ids)
                    ))
                    
                    session.execute(delete(WorkflowExecution).where(
                        WorkflowExecution.id.in_(execution_ids)
                    ))
                    
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
                batch_time = time.time() - batch_start_time
                elapsed = time.time() - start_time_func
                rate = processed_count / elapsed if elapsed > 0 else 0
                batch_rate = actual_batch_size / batch_time if batch_time > 0 else 0
                pct_complete = (processed_count / total_count) * 100 if total_count and total_count > 0 else 0
                
                logger.info(
                    f"Batch {batch_count}: Processed {processed_count}/{total_count or 'unknown'} executions "
                    f"({pct_complete:.2f}%) at {rate:.2f} records/sec overall, {batch_rate:.2f} records/sec this batch. "
                    f"Batch contained {actual_batch_size} executions, {logs_count} logs, "
                    f"{alert_executions_count} alert links, {incident_executions_count} incident links"
                )
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error processing batch {batch_count}: {str(e)}")
                # Continue with next batch rather than failing completely
                # Add a small delay to prevent hammering the database on errors
                time.sleep(2)
    
    # Final stats
    elapsed = time.time() - start_time_func
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


def parallel_cleanup_workflow_executions(
    retention_days: int = 30,
    batch_size: int = 5000,
    dry_run: bool = False,
    num_processes: int = 4,
    skip_count: bool = False
):
    """
    Cleanup function that uses multiple processes to delete workflow executions.
    
    Args:
        retention_days: Number of days to retain workflow executions
        batch_size: Size of batches for deletion
        dry_run: If True, only simulate deletion
        num_processes: Number of parallel processes to use
        skip_count: Skip the initial count query for better performance
    """
    # Default to half of available CPUs if not specified
    if num_processes <= 0:
        num_processes = max(1, multiprocessing.cpu_count() // 2)
    
    logger.info(f"Starting parallel cleanup with {num_processes} processes")
    logger.info(f"Retention days: {retention_days}, batch size: {batch_size}, dry run: {dry_run}")
    
    # For UUID fields, we'll use a different approach for parallelism
    # We'll slice the execution time range instead of using ID modulo
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    time_span = datetime.utcnow() - cutoff_date
    
    # Calculate time slices for each process
    processes = []
    statuses = [
        ["complete", "success", "completed"],
        ["failed", "error"]
    ]
    
    if num_processes > 1:
        # Create one process per time slice and status group combination
        for status_group in statuses:
            for i in range(num_processes):
                # Calculate a time slice for this process
                slice_start = cutoff_date + (time_span * i // num_processes)
                slice_end = cutoff_date + (time_span * (i + 1) // num_processes)
                
                if i == num_processes - 1:
                    # Make sure the last slice includes everything up to now
                    slice_end = datetime.utcnow() + timedelta(minutes=1)  # Add a minute buffer
                
                p = multiprocessing.Process(
                    target=_cleanup_process_worker_time_slice,
                    args=(slice_start, slice_end, batch_size, dry_run, i, status_group, skip_count)
                )
                processes.append(p)
                p.start()
    else:
        # Just one process - do everything
        for status_group in statuses:
            p = multiprocessing.Process(
                target=_cleanup_process_worker_time_slice,
                args=(cutoff_date, datetime.utcnow() + timedelta(minutes=1), batch_size, dry_run, 0, status_group, skip_count)
            )
            processes.append(p)
            p.start()
    
    # Wait for all processes to complete
    for p in processes:
        p.join()
    
    logger.info("Parallel cleanup complete!")


def _cleanup_process_worker_time_slice(start_time, end_time, batch_size, dry_run, process_id, status_group, skip_count):
    """Helper function for parallel cleanup using time slices - runs in a separate process"""
    logger.info(f"Worker {process_id} starting - Time range: {start_time} to {end_time} - Status: {status_group}")
    
    engine, session = get_db_connection()
    
    criteria = {}
    
    # Each worker will process a specific time slice
    batch_delete_workflow_executions(
        session=session,
        criteria=criteria,
        batch_size=batch_size,
        dry_run=dry_run,
        start_time=start_time,
        end_time=end_time,
        status_filter=status_group,
        skip_count=skip_count
    )
    
    logger.info(f"Worker {process_id} finished")


def cleanup_old_workflow_executions(
    retention_days: int = 30,
    batch_size: int = 5000,
    dry_run: bool = False,
    parallel: bool = False,
    num_processes: int = 4,
    skip_count: bool = False
):
    """
    Cleanup function to delete workflow executions older than specified retention period.
    
    Args:
        retention_days: Number of days to retain workflow executions
        batch_size: Size of batches for deletion
        dry_run: If True, only simulate deletion
        parallel: Use parallel processing for faster deletion
        num_processes: Number of parallel processes to use
        skip_count: Skip initial counting for performance
    """
    if parallel:
        return parallel_cleanup_workflow_executions(
            retention_days=retention_days,
            batch_size=batch_size,
            dry_run=dry_run,
            num_processes=num_processes,
            skip_count=skip_count
        )
    
    engine, Session = get_db_connection()
    
    logger.info(f"Starting cleanup of workflow executions older than {retention_days} days")
    logger.info(f"batch_size: {batch_size}")
    logger.info(f"dry_run: {dry_run}")
    
    # Delete completed executions
    logger.info("Processing completed executions...")
    completed_count = batch_delete_workflow_executions(
        session=Session,
        criteria={},
        batch_size=batch_size,
        dry_run=dry_run,
        age_days=retention_days,
        status_filter=["complete", "success", "completed"],
        skip_count=skip_count
    )
    
    # Delete failed executions (might want different retention policy)
    logger.info("Processing failed executions...")
    failed_count = batch_delete_workflow_executions(
        session=Session,
        criteria={},
        batch_size=batch_size,
        dry_run=dry_run,
        age_days=retention_days,  # Could use a different retention for failed ones
        status_filter=["failed", "error"],
        skip_count=skip_count
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
    parser.add_argument("--batch-size", type=int, default=5000, help="Batch size for deletion")
    parser.add_argument("--dry-run", action="store_true", help="Simulate deletion without actually deleting")
    parser.add_argument("--workflow-id", help="Limit deletion to a specific workflow ID")
    parser.add_argument("--parallel", action="store_true", help="Use parallel processing for faster deletion")
    parser.add_argument("--processes", type=int, default=4, help="Number of processes for parallel mode")
    parser.add_argument("--skip-count", action="store_true", help="Skip counting for better performance")
    
    args = parser.parse_args()
    
    if args.workflow_id:
        # Delete executions for a specific workflow
        engine, session = get_db_connection()
        batch_delete_workflow_executions(
            session=session,
            criteria={"workflow_id": args.workflow_id},
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            age_days=args.retention_days,
            skip_count=args.skip_count
        )
    else:
        # Run the general cleanup
        cleanup_old_workflow_executions(
            retention_days=args.retention_days,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            parallel=args.parallel,
            num_processes=args.processes,
            skip_count=args.skip_count
        )