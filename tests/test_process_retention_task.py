import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from keep.api.tasks import process_retention_task


def test_process_retention_skips_when_disabled():
    with (
        patch.object(process_retention_task, "KEEP_ALERT_RETENTION_DAYS", 0),
        patch.object(process_retention_task, "get_tenants") as get_tenants,
        patch.object(
            process_retention_task, "delete_alerts_by_retention"
        ) as delete_alerts,
    ):
        process_retention_task.process_retention(MagicMock())

    get_tenants.assert_not_called()
    delete_alerts.assert_not_called()


def test_process_retention_applies_policy_to_each_tenant():
    fixed_now = datetime(2026, 7, 26, 12, 0, 0)
    datetime_class = MagicMock(wraps=datetime)
    datetime_class.utcnow.return_value = fixed_now
    logger = MagicMock()

    with (
        patch.object(process_retention_task, "KEEP_ALERT_RETENTION_DAYS", 30),
        patch.object(process_retention_task, "KEEP_ALERT_RETENTION_BATCH_SIZE", 25),
        patch.object(process_retention_task.datetime, "datetime", datetime_class),
        patch.object(
            process_retention_task,
            "get_tenants",
            return_value=[
                SimpleNamespace(id="tenant-with-expired-alerts"),
                SimpleNamespace(id="tenant-without-expired-alerts"),
            ],
        ),
        patch.object(
            process_retention_task,
            "delete_alerts_by_retention",
            side_effect=[3, 0],
        ) as delete_alerts,
    ):
        process_retention_task.process_retention(logger)

    purge_before = fixed_now - timedelta(days=30)
    assert delete_alerts.call_args_list == [
        call("tenant-with-expired-alerts", purge_before, 25),
        call("tenant-without-expired-alerts", purge_before, 25),
    ]
    logger.info.assert_called_once_with(
        "Deleted alerts by retention policy",
        extra={"tenant_id": "tenant-with-expired-alerts", "deleted": 3},
    )


@pytest.mark.asyncio
async def test_redis_retention_skips_when_lock_is_held():
    redis_instance = AsyncMock()
    redis_instance.set.return_value = False
    process = MagicMock()

    with (
        patch.object(process_retention_task, "REDIS", True),
        patch.object(process_retention_task, "process_retention", process),
    ):
        await process_retention_task.async_process_retention(
            {"redis": redis_instance, "pool": None}
        )

    redis_instance.set.assert_awaited_once_with(
        "lock:retention:process", "1", ex=3600, nx=True
    )
    process.assert_not_called()
    redis_instance.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_redis_retention_runs_in_pool_and_releases_lock():
    redis_instance = AsyncMock()
    redis_instance.set.return_value = True
    pool = MagicMock()
    loop = MagicMock()
    loop.run_in_executor = AsyncMock()
    process = MagicMock()

    with (
        patch.object(process_retention_task, "REDIS", True),
        patch.object(process_retention_task, "process_retention", process),
        patch.object(
            process_retention_task.asyncio,
            "get_running_loop",
            return_value=loop,
        ),
    ):
        await process_retention_task.async_process_retention(
            {"redis": redis_instance, "pool": pool}
        )

    loop.run_in_executor.assert_awaited_once_with(
        pool, process, process_retention_task.logger
    )
    redis_instance.delete.assert_awaited_once_with("lock:retention:process")


@pytest.mark.asyncio
async def test_redis_retention_releases_lock_after_failure():
    redis_instance = AsyncMock()
    redis_instance.set.return_value = True
    loop = MagicMock()
    loop.run_in_executor = AsyncMock(side_effect=RuntimeError("retention failed"))

    with (
        patch.object(process_retention_task, "REDIS", True),
        patch.object(
            process_retention_task.asyncio,
            "get_running_loop",
            return_value=loop,
        ),
        pytest.raises(RuntimeError, match="retention failed"),
    ):
        await process_retention_task.async_process_retention(
            {"redis": redis_instance, "pool": None}
        )

    redis_instance.delete.assert_awaited_once_with("lock:retention:process")


@pytest.mark.asyncio
async def test_local_retention_runs_once_before_sleeping():
    lock = MagicMock()
    loop = MagicMock()
    loop.run_in_executor = AsyncMock()
    sleep = AsyncMock(side_effect=asyncio.CancelledError)
    process = MagicMock()

    with (
        patch.object(process_retention_task, "REDIS", False),
        patch.object(process_retention_task, "KEEP_ALERT_RETENTION_INTERVAL", 60),
        patch.object(
            process_retention_task, "FileLock", return_value=lock
        ) as file_lock,
        patch.object(process_retention_task, "process_retention", process),
        patch.object(
            process_retention_task.asyncio,
            "get_running_loop",
            return_value=loop,
        ),
        patch.object(process_retention_task.asyncio, "sleep", sleep),
        pytest.raises(asyncio.CancelledError),
    ):
        await process_retention_task.async_process_retention()

    file_lock.assert_called_once_with("/tmp/retention_process.lock", timeout=30)
    loop.run_in_executor.assert_awaited_once_with(
        None, process, process_retention_task.logger
    )
    sleep.assert_awaited_once()
    assert 0 <= sleep.await_args.args[0] <= 60
