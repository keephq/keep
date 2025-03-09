import enum


class ActionType(enum.Enum):
    # the alert was triggered
    TIGGERED = "alert was triggered"
    # someone acknowledged the alert
    ACKNOWLEDGE = "alert acknowledged"
    # the alert was resolved
    AUTOMATIC_RESOLVE = "alert automatically resolved"
    API_AUTOMATIC_RESOLVE = "alert automatically resolved by API"
    # the alert was resolved manually
    MANUAL_RESOLVE = "alert manually resolved"
    MANUAL_STATUS_CHANGE = "alert status manually changed"
    API_STATUS_CHANGE = "alert status changed by API"
    STATUS_UNENRICH = "alert status undone"
    # the alert was escalated
    WORKFLOW_ENRICH = "alert enriched by workflow"
    MAPPING_RULE_ENRICH = "alert enriched by mapping rule"
    EXTRACTION_RULE_ENRICH = "alert enriched by extraction rule"
    # the alert was deduplicated
    DEDUPLICATED = "alert was deduplicated"
    # a ticket was created
    TICKET_ASSIGNED = "alert was assigned with ticket"
    TICKET_UNASSIGNED = "alert was unassigned from ticket"
    # a ticket was updated
    TICKET_UPDATED = "alert ticket was updated"
    # disposing enriched alert
    DISPOSE_ENRICHED_ALERT = "alert enrichments disposed"
    # delete alert
    DELETE_ALERT = "alert deleted"
    # generic enrichment
    GENERIC_ENRICH = "alert enriched"
    GENERIC_UNENRICH = "alert un-enriched"
    # commented
    COMMENT = "a comment was added to the alert"
    UNCOMMENT = "a comment was removed from the alert"
    MAINTENANCE = "Alert is in maintenance window"
    INCIDENT_COMMENT = "A comment was added to the incident"
    INCIDENT_ENRICH = "Incident enriched"
    INCIDENT_STATUS_CHANGE = "Incident status changed"
    INCIDENT_ASSIGN = "Incident assigned"
