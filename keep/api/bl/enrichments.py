import logging

from sqlmodel import Session

from keep.api.core.db import enrich_alert
from keep.api.models.alert import AlertDto
from keep.api.models.db.mapping import MappingRule


class EnrichmentsBl:
    def __init__(self, tenant_id: str, db: Session):
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id
        self.db_session = db

    def run_mapping_rules(self, alert: AlertDto):
        """
        Run the mapping rules for the alert
        """
        self.logger.info(
            "Running mapping rules for incoming alert",
            extra={"fingerprint": alert.fingerprint},
        )
        rules: list[MappingRule] = (
            self.db_session.query(MappingRule)
            .filter(MappingRule.tenant_id == self.tenant_id)
            .filter(MappingRule.disabled == False)
            .all()
        )

        if not rules:
            self.logger.debug("No mapping rules found for tenant")
            return alert

        for rule in rules:
            # Check if the alert has all the required attributes from matchers
            if not all(hasattr(alert, attribute) for attribute in rule.matchers):
                self.logger.debug(
                    "Alert does not have all the required attributes for the rule",
                    extra={"fingerprint": alert.fingerprint},
                )
                continue

            # Check if the alert matches any of the rows
            for row in rule.rows:
                if all(
                    getattr(alert, attribute) == row.get(attribute)
                    for attribute in rule.matchers
                ):
                    self.logger.info(
                        "Alert matched a mapping rule, enriching...",
                        extra={"fingerprint": alert.fingerprint},
                    )
                    # This is where you match the row, add your enrichment logic here
                    # For example: alert.enrich(row)
                    # Remember to break if you only need the first match or adjust logic as needed
                    enrichments = {
                        key: value
                        for key, value in row.items()
                        if key not in rule.matchers
                    }
                    enrich_alert(self.tenant_id, alert.fingerprint, enrichments)
                    self.logger.info(
                        "Alert enriched", extra={"fingerprint": alert.fingerprint}
                    )
                    break
