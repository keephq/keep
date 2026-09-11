import asyncio

import pytest

from keep.api import api


@pytest.mark.asyncio
async def test_create_service_task_holds_strong_reference():
    started = asyncio.Event()
    release = asyncio.Event()

    async def service():
        started.set()
        await release.wait()

    task = api.create_service_task(service())
    await started.wait()

    # the task is strongly referenced while running, so the event loop's
    # weak reference is not the only thing keeping it alive
    assert task in api.service_tasks

    release.set()
    await task

    # completed tasks are discarded so the set doesn't grow unboundedly
    assert task not in api.service_tasks
