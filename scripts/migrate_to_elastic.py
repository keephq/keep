# Description: Script to migrate data from the database to ElasticSearch
import os

from dateutil import parser
from dateutil.parser import ParserError
from dotenv import load_dotenv

from keep.api.core.db import get_alerts_with_filters
from keep.api.core.elastic import ElasticClient
from keep.api.models.alert import AlertDto
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts

load_dotenv()
TENANT_ID = os.environ.get("MIGRATION_TENANT_ID")
TENANT_ID = "1f1365c0-247d-448f-9554-ef6c50853239"


def format_datetime_fields(alert: AlertDto) -> AlertDto:
    for attr_name, attr_value in alert.__dict__.items():
        if isinstance(attr_value, str):
            try:
                # Try to parse the string as a datetime
                parsed_date = parser.parse(attr_value)
                # Format the datetime to ISO 8601 with timezone information
                formatted_value = parsed_date.isoformat()
                setattr(alert, attr_name, formatted_value)
            except ParserError:
                # If parsing fails, it's not a datetime string, so we skip it
                continue
    return alert


if __name__ == "__main__":
    # dismissedUntil + group last_updated_time + split to 500
    elastic_client = ElasticClient(TENANT_ID)
    alerts = get_alerts_with_filters(TENANT_ID, time_delta=365)  # year ago
    print(f"Found {len(alerts)} alerts")
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    print(f"Converted {len(alerts_dto)} alerts")

    # Format datetime fields
    alerts_dto = [format_datetime_fields(alert) for alert in alerts_dto]

    # filter out alerts that dismissUntil is '' (empty string) since its not a valid datetime anymore
    _alerts_dto = []
    for alert in alerts_dto:
        if hasattr(alert, "dismissUntil") and alert.dismissUntil == "":
            continue
        _alerts_dto.append(alert)

    alerts_dto = _alerts_dto

    # Sort by timestamp desc:
    alerts_dto = sorted(alerts_dto, key=lambda x: x.lastReceived, reverse=True)
    # Take only the first one for each fingerprint:
    alerts_dto = {alert.fingerprint: alert for alert in alerts_dto}.values()

    # elastic_client.create_index(tenant_id=TENANT_ID)
    elastic_client.index_alerts(alerts_dto)
    print("Done")
