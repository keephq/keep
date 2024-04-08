import logging

from sqlmodel import Session

from keep.api.core.db import enrich_alert
from keep.api.models.alert import AlertDto
from keep.api.models.db.mapping import MappingRule


def get_nested_attribute(obj: AlertDto, attr_path: str):
    """
    Recursively get a nested attribute
    """
    # Special case for source, since it's a list
    if attr_path == "source" and obj.source is not None and len(obj.source) > 0:
        return obj.source[0]
    attributes = attr_path.split(".")
    for attr in attributes:
        # @@ is used as a placeholder for . in cases where the attribute name has a .
        # For example, we have {"results": {"some.attribute": "value"}}
        # We can access it by using "results.some@@attribute" so we won't think its a nested attribute
        if attr is not None and "@@" in attr:
            attr = attr.replace("@@", ".")
        obj = getattr(obj, attr, obj.get(attr) if isinstance(obj, dict) else None)
        if obj is None:
            return None
    return obj


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
            .order_by(MappingRule.priority.desc())
            .all()
        )

        if not rules:
            self.logger.debug("No mapping rules found for tenant")
            return alert

        for rule in rules:
            # Check if the alert has all the required attributes from matchers
            if not all(
                get_nested_attribute(alert, attribute) for attribute in rule.matchers
            ):
                self.logger.debug(
                    "Alert does not have all the required attributes for the rule",
                    extra={"fingerprint": alert.fingerprint},
                )
                continue

            # Check if the alert matches any of the rows
            for row in rule.rows:
                if all(
                    get_nested_attribute(alert, attribute) == row.get(attribute)
                    or row.get(attribute) == "*"  # Wildcard
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

                    # Enrich the alert with the matched row
                    for key, value in enrichments.items():
                        setattr(alert, key, value)

                    # Save the enrichments to the database
                    enrich_alert(
                        self.tenant_id, alert.fingerprint, enrichments, self.db_session
                    )
                    self.logger.info(
                        "Alert enriched", extra={"fingerprint": alert.fingerprint}
                    )
                    break
