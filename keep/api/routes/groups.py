import logging

import chevron
from fastapi import APIRouter, Depends

from keep.api.core.db import get_groups as get_groups_db
from keep.api.core.db import get_rule as get_rule_db
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.models.group import AlertSummaryDto, GroupDto

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    description="Get groups",
)
def get_groups(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> list[dict]:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching groups",
        extra={
            "tenant_id": tenant_id,
        },
    )
    # first, get groups
    groups = get_groups_db(tenant_id)
    groups_dtos = []
    # build the group dto
    for group in groups:
        rule = get_rule_db(tenant_id, group.rule_id)
        # calc the group start time and last update time from the alerts
        # TODO: group should expose fields and how it calculates them
        #       now we "support" start_time,
        group_attributes = GroupDto.get_group_attributes(group.alerts)
        context = {
            "group": group_attributes,
            # Shahar: first, group have at least one alert.
            #         second, the only supported {{ }} are the ones in the group
            #          attributes, so we can use the first alert because they are the same for any other alert in the group
            **group.alerts[0].event,
        }
        group_description = chevron.render(rule.group_description, context)
        alerts_summary_dtos = []
        for alert in group.alerts:
            # render the alert summary
            alert_summary = chevron.render(rule.item_description, alert.event)
            alert_summary_dto = AlertSummaryDto(
                alert_summary=alert_summary,
                alert_fingerprint=alert.fingerprint,
            )
            alerts_summary_dtos.append(alert_summary_dto)
        group_dto = GroupDto(
            group_description=group_description,
            start_time=group_attributes.get("start_time"),
            last_update_time=group_attributes.get("last_update_time"),
            alerts=alerts_summary_dtos,
        )
        groups_dtos.append(group_dto)
    # last, process the alerts and return the groups
    return groups_dtos
