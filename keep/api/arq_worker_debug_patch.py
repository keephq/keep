import functools
import logging
import time
from typing import Optional

from arq.worker import Worker

# Set up detailed logging
logging_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.DEBUG, format=logging_format)
debug_logger = logging.getLogger("arq.debug")

# Original methods we'll patch
original_run_job = Worker.run_job
original_finish_job = Worker.finish_job
original_start_jobs = Worker.start_jobs

# Tracking in-progress jobs for additional context
in_progress_jobs = {}


def log_function_call(func):
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        job_id = args[0] if args else None
        debug_logger.info(f"ENTER: {func.__name__} for job {job_id}")

        # Log arguments
        debug_logger.debug(f"ARGS: {func.__name__} - {args}")
        debug_logger.debug(f"KWARGS: {func.__name__} - {kwargs}")

        start_time = time.time()
        try:
            result = await func(self, *args, **kwargs)
            debug_logger.info(
                f"EXIT: {func.__name__} for job {job_id} in {time.time() - start_time:.4f}s"
            )
            return result
        except Exception as e:
            debug_logger.exception(f"ERROR in {func.__name__} for job {job_id}: {e}")
            raise

    return wrapper


# Patch run_job method to add extensive logging
async def patched_run_job(self, job_id: str, score: int) -> None:
    debug_logger.info(f"🔍 JOB START: {job_id} with score {score}")

    # Record job start time and info
    in_progress_jobs[job_id] = {
        "start_time": time.time(),
        "score": score,
        "attempts": 0,
    }

    # Get redis retry counter
    retry_key = "arq:retry:" + job_id
    try:
        retry_count = await self.pool.get(retry_key)
        debug_logger.info(f"🔢 Current retry count for {job_id}: {retry_count}")
    except Exception as e:
        debug_logger.warning(f"Could not get retry count for {job_id}: {e}")

    # Log any existing in-progress markers
    in_progress_key = "arq:in-progress:" + job_id
    try:
        in_progress_exists = await self.pool.exists(in_progress_key)
        debug_logger.info(
            f"🏁 In-progress key exists for {job_id}: {in_progress_exists}"
        )
        if in_progress_exists:
            ttl = await self.pool.pttl(in_progress_key)
            debug_logger.info(f"⏱️ In-progress TTL for {job_id}: {ttl}ms")
    except Exception as e:
        debug_logger.warning(f"Could not check in-progress for {job_id}: {e}")

    # Run the original method
    try:
        await original_run_job(self, job_id, score)
    finally:
        if job_id in in_progress_jobs:
            duration = time.time() - in_progress_jobs[job_id]["start_time"]
            debug_logger.info(f"🏁 JOB END: {job_id} took {duration:.4f}s")
            in_progress_jobs.pop(job_id, None)


# Patch finish_job to track job completion
async def patched_finish_job(
    self,
    job_id: str,
    finish: bool,
    result_data: Optional[bytes],
    result_timeout_s: Optional[float],
    keep_result_forever: bool,
    incr_score: Optional[int],
    keep_in_progress: Optional[float],
) -> None:
    debug_logger.info(
        f"💾 FINISH JOB {job_id}: finish={finish}, incr_score={incr_score}, "
        f"keep_in_progress={keep_in_progress}"
    )

    # Inspect transaction before it happens
    in_progress_key = "arq:in-progress:" + job_id
    retry_key = "arq:retry:" + job_id
    queue_key = self.queue_name

    # Log Redis state before transaction
    debug_logger.info(f"📊 REDIS STATE BEFORE FINISH for {job_id}:")
    try:
        exists_progress = await self.pool.exists(in_progress_key)
        exists_retry = await self.pool.exists(retry_key)
        job_in_queue = await self.pool.zscore(queue_key, job_id)

        debug_logger.info(f"  - In-progress exists: {exists_progress}")
        debug_logger.info(f"  - Retry key exists: {exists_retry}")
        debug_logger.info(f"  - Job in queue score: {job_in_queue}")

        if exists_retry:
            retry_value = await self.pool.get(retry_key)
            debug_logger.info(f"  - Retry count: {retry_value}")
    except Exception as e:
        debug_logger.exception(f"Error checking Redis state: {e}")

    try:
        await original_finish_job(
            self,
            job_id,
            finish,
            result_data,
            result_timeout_s,
            keep_result_forever,
            incr_score,
            keep_in_progress,
        )
    finally:
        # Log Redis state after transaction
        debug_logger.info(f"📊 REDIS STATE AFTER FINISH for {job_id}:")
        try:
            exists_progress = await self.pool.exists(in_progress_key)
            exists_retry = await self.pool.exists(retry_key)
            job_in_queue = await self.pool.zscore(queue_key, job_id)

            debug_logger.info(f"  - In-progress exists: {exists_progress}")
            debug_logger.info(f"  - Retry key exists: {exists_retry}")
            debug_logger.info(f"  - Job in queue score: {job_in_queue}")
        except Exception as e:
            debug_logger.exception(f"Error checking Redis state: {e}")


# Patch start_jobs to monitor job pickup
async def patched_start_jobs(self, job_ids: list) -> None:
    if job_ids:
        debug_logger.info(f"🔍 STARTING JOBS: Found {len(job_ids)} jobs to process")
        for job_id_bytes in job_ids:
            job_id = job_id_bytes.decode()
            debug_logger.info(f"🔍 JOB PICKUP: {job_id}")

    await original_start_jobs(self, job_ids)


# Patch the pipeline to capture Redis watch errors
original_pipeline_execute = None


async def patched_pipeline_execute(self, *args, **kwargs):
    try:
        result = await original_pipeline_execute(self, *args, **kwargs)
        debug_logger.debug(f"Pipeline executed successfully: {result}")
        return result
    except Exception as e:
        debug_logger.warning(f"Pipeline execution failed: {e}")
        debug_logger.warning(f"Pipeline commands: {self.command_stack}")
        raise


# Apply the patches
def apply_arq_debug_patches():
    debug_logger.info("🛠️ Applying ARQ debug patches")

    # Apply basic logging to key methods
    for method_name in ["_poll_iteration", "heart_beat", "main"]:
        original = getattr(Worker, method_name)
        setattr(Worker, method_name, log_function_call(original))

    # Apply our custom patches
    Worker.run_job = patched_run_job
    Worker.finish_job = patched_finish_job
    Worker.start_jobs = patched_start_jobs

    # Patch the Redis pipeline when the worker starts up
    original_main = Worker.main

    async def patched_main(self):
        global original_pipeline_execute
        # Now we can safely patch the pipeline execute method
        from redis import asyncio as aioredis

        pipeline_cls = aioredis.client.Pipeline
        original_pipeline_execute = pipeline_cls.execute
        pipeline_cls.execute = patched_pipeline_execute

        # Add patches for watch errors
        original_watch = aioredis.client.Redis.watch

        async def patched_watch(self, *keys):
            debug_logger.info(f"👀 REDIS WATCH: watching keys {keys}")
            return await original_watch(self, *keys)

        aioredis.client.Redis.watch = patched_watch

        debug_logger.info("✅ Redis pipeline and watch methods patched")

        # Call the original main method
        return await original_main(self)

    Worker.main = patched_main

    debug_logger.info("✅ ARQ debug patches applied")


# Patch process_event_task.py to track possible Retry exceptions
def patch_process_event():
    try:
        from keep.api.tasks.process_event_task import process_event

        original_process_event = process_event

        def patched_process_event(*args, **kwargs):
            debug_logger.info(
                f"🔄 PROCESS_EVENT called with args={args}, kwargs={kwargs}"
            )
            try:
                result = original_process_event(*args, **kwargs)
                debug_logger.info(f"✅ PROCESS_EVENT completed successfully: {result}")
                return result
            except Exception as e:
                debug_logger.exception(f"❌ PROCESS_EVENT failed: {e}")
                raise

        from keep.api.tasks import process_event_task

        process_event_task.process_event = patched_process_event
        debug_logger.info("✅ Patched process_event function")
    except ImportError:
        debug_logger.warning("⚠️ Could not patch process_event (import failed)")


# Add a helper function to dump Redis state for a job
async def dump_job_state(redis_pool, job_id: str):
    """Dump all Redis keys related to a specific job"""
    debug_logger.info(f"📊 DUMPING STATE FOR JOB {job_id}")

    # Define key prefixes
    prefixes = [
        "arq:job:",
        "arq:result:",
        "arq:retry:",
        "arq:in-progress:",
        "arq:abort-jobs",
    ]

    # Check queue
    queues = await redis_pool.keys("arq:queue:*")
    for queue in queues:
        score = await redis_pool.zscore(queue, job_id)
        if score:
            debug_logger.info(f"Job {job_id} found in queue {queue} with score {score}")

    # Check all relevant keys
    for prefix in prefixes:
        key = prefix + job_id
        exists = await redis_pool.exists(key)
        if exists:
            value = await redis_pool.get(key)
            debug_logger.info(f"Key {key} exists with value: {value}")
            ttl = await redis_pool.ttl(key)
            debug_logger.info(f"TTL for {key}: {ttl}s")
