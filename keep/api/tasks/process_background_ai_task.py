import logging
import datetime

from keep.api.utils.import_ee import mine_incidents_and_create_objects, ALGORITHM_VERBOSE_NAME
from keep.api.core.db import get_tenants_configurations

logger = logging.getLogger(__name__)


async def process_background_ai_task(
        ctx: dict | None,  # arq context
    ):
    if mine_incidents_and_create_objects is not NotImplemented:
        for tenant in get_tenants_configurations():
            logger.info(
                f"Background AI task finished, {ALGORITHM_VERBOSE_NAME}",
                extra={"algorithm": ALGORITHM_VERBOSE_NAME, "tenant_id": tenant},
            )
            start_time = datetime.datetime.now()
            await mine_incidents_and_create_objects(
                ctx,
                tenant_id=tenant
            )
            end_time = datetime.datetime.now()
            logger.info(
                f"Background AI task finished, {ALGORITHM_VERBOSE_NAME}, took {(end_time - start_time).total_seconds()} seconds",
                extra={
                    "algorithm": ALGORITHM_VERBOSE_NAME,
                    "tenant_id": tenant, 
                    "duration_ms": (end_time - start_time).total_seconds() * 1000
                },
            )
