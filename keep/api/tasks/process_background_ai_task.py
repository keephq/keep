import time
import logging
import datetime

from keep.api.core.tenant_configuration import TenantConfiguration
from keep.api.utils.import_ee import mine_incidents_and_create_objects, ALGORITHM_VERBOSE_NAME, \
    SUMMARY_GENERATOR_VERBOSE_NAME, NAME_GENERATOR_VERBOSE_NAME, is_ee_enabled_for_tenant, generate_update_incident_summary, generate_update_incident_name
from keep.api.core.db import get_tenants_configurations

logger = logging.getLogger(__name__)


async def process_correlation(ctx, tenant_id:str):
    logger.info(
        f"Background AI task started, {ALGORITHM_VERBOSE_NAME}",
        extra={"algorithm": ALGORITHM_VERBOSE_NAME, "tenant_id": tenant_id},
    )
    start_time = datetime.datetime.now()
    await mine_incidents_and_create_objects(
        ctx,
        tenant_id=tenant_id
    )
    end_time = datetime.datetime.now()
    logger.info(
        f"Background AI task finished, {ALGORITHM_VERBOSE_NAME}, took {(end_time - start_time).total_seconds()} seconds",
        extra={
            "algorithm": ALGORITHM_VERBOSE_NAME,
            "tenant_id": tenant_id, 
            "duration_ms": (end_time - start_time).total_seconds() * 1000
        },
    )

async def process_summary_generation(ctx, tenant_id: str, incident_id:str):
    logger.info(
        f"Background summary generation started, {SUMMARY_GENERATOR_VERBOSE_NAME}",
        extra={"algorithm": SUMMARY_GENERATOR_VERBOSE_NAME, "incident_id": incident_id},
    )
    
    start_time = datetime.datetime.now()
    await generate_update_incident_summary(
        ctx,
        tenant_id=tenant_id,
        incident_id=incident_id
    )
    end_time = datetime.datetime.now()
    logger.info(
        f"Background summary generation finished, {SUMMARY_GENERATOR_VERBOSE_NAME}, took {(end_time - start_time).total_seconds()} seconds",
        extra={
            "algorithm": SUMMARY_GENERATOR_VERBOSE_NAME,
            "incident_id": incident_id, 
            "duration_ms": (end_time - start_time).total_seconds() * 1000
        },
    )
    
async def process_name_generation(ctx, tenant_id: str, incident_id: str):
    logger.info(
        f"Background name generation started, {NAME_GENERATOR_VERBOSE_NAME}",
        extra={"algorithm": NAME_GENERATOR_VERBOSE_NAME, "incident_id": incident_id},
    )
    
    start_time = datetime.datetime.now()
    await generate_update_incident_name(
        ctx,
        tenant_id=tenant_id,
        incident_id=incident_id
    )
    end_time = datetime.datetime.now()
    logger.info(
        f"Background name generation finished, {NAME_GENERATOR_VERBOSE_NAME}, took {(end_time - start_time).total_seconds()} seconds",
        extra={
            "algorithm": NAME_GENERATOR_VERBOSE_NAME,
            "incident_id": incident_id, 
            "duration_ms": (end_time - start_time).total_seconds() * 1000
        },
    )
    

async def process_background_ai_task(
        ctx: dict | None,  # arq context
    ):
    """
    This job will schedule the process_correlation job for each tenant with strict ID's.
    This ensures that the job is not scheduled multiple times for the same tenant.
    """
    pool = ctx["redis"]
    try:
        all_jobs = await pool.queued_jobs()
    except Exception as e:
        logger.error(f"Error getting queued jobs, happens sometimes with unknown reason: {e}")
        return None
    
    tenant_configuration = TenantConfiguration()

    if mine_incidents_and_create_objects is not NotImplemented:
        tenants = get_tenants_configurations(only_with_config=True)
        for tenant in tenants:
            if is_ee_enabled_for_tenant(tenant, tenant_configuration=tenant_configuration):
                # Because of https://github.com/python-arq/arq/issues/432 we need to check if the job is already running
                # The other option would be to twick "keep_result" but it will make debugging harder
                job_prefix = 'process_correlation_tenant_id_' + str(tenant)
                jobs_with_same_prefix = [job for job in all_jobs if job.job_id.startswith(job_prefix)]
                if len(jobs_with_same_prefix) > 0:
                    logger.info(
                        f"No {ALGORITHM_VERBOSE_NAME} for tenant {tenant} scheduled because there is already one running",
                        extra={"algorithm": ALGORITHM_VERBOSE_NAME, "tenant_id": tenant},
                    )
                else:
                    job = await pool.enqueue_job(
                        "process_correlation",
                        tenant_id=tenant,
                        _job_id=job_prefix + ":" + str(time.time()), # Strict ID ensures uniqueness
                        _job_try=1
                    )
                    logger.info(
                        f"{ALGORITHM_VERBOSE_NAME} for tenant {tenant} scheduled, job: {job}",
                        extra={"algorithm": ALGORITHM_VERBOSE_NAME, "tenant_id": tenant},
                    )
            else:
                logger.info(
                    f"No {ALGORITHM_VERBOSE_NAME} for tenant {tenant} scheduled because EE is disabled for this tenant",
                    extra={"algorithm": ALGORITHM_VERBOSE_NAME, "tenant_id": tenant},
                )
