# Description: Script to migrate data from the database to ElasticSearch
import os

from dateutil import parser
from dateutil.parser import ParserError
from dotenv import load_dotenv

from keep.api.consts import STATIC_PRESETS
from keep.api.core.db import get_alerts_with_filters
from keep.api.core.elastic import ElasticClient
from keep.api.models.alert import AlertDto
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.searchengine.searchengine import SearchEngine

load_dotenv()
TENANT_ID = os.environ.get("MIGRATION_TENANT_ID")

# os.environ["DATABASE_ECHO"] = "true"
# MAKE SURE TO DISBALE SOME DYNAMIC MAPPINGS IN ELASTICSEARCH
# E.G.
# PUT /keep-alerts-TENANT-ID
# {
#   "mappings": {
#     "properties": {
#       "result": {
#         "type": "object",
#         "dynamic": "false"
#       },
#       "kubernetes": {
#         "type": "object",
#         "dynamic": "false"
#       },
#       "dimensions": {
#         "type": "object",
#         "dynamic": "false"
#       },
#       "inputs": {
#         "type": "object",
#         "dynamic": "false"
#       },
#       "tags": {
#         "type": "object",
#         "dynamic": "false"
#       },
#       "exceptions": {
#         "type": "object",
#         "dynamic": "false"
#       }
#     }
#   }
# }


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
            except Exception:
                pass
    return alert


"""
def change_keys_recursively(data):
    if isinstance(data, dict):
        new_data = {}
        for key, value in data.items():
            new_key = key.replace('.', '_')
            new_data[new_key] = change_keys_recursively(value)
        return new_data
    elif isinstance(data, list):
        return [change_keys_recursively(item) for item in data]
    else:
        return data
"""

if __name__ == "__main__":
    # dismissedUntil + group last_updated_time + split to 500

    elastic_client = ElasticClient(TENANT_ID)

    preset = STATIC_PRESETS["feed"]
    search_engine = SearchEngine(tenant_id=TENANT_ID)
    search_engine.search_alerts(preset.query)
    # get the number of alerts + noisy alerts for each preset

    alerts = get_alerts_with_filters(TENANT_ID, time_delta=365, with_incidents=True)  # year ago
    print(f"Found {len(alerts)} alerts")
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts, with_incidents=True)
    print(f"Converted {len(alerts_dto)} alerts")

    # Format datetime fields
    alerts_dto = [format_datetime_fields(alert) for alert in alerts_dto]
    print(f"Formatted datetime fields for {len(alerts_dto)} alerts")
    # filter out alerts that dismissUntil is '' (empty string) since its not a valid datetime anymore
    _alerts_dto = []
    for alert in alerts_dto:
        if hasattr(alert, "dismissUntil") and alert.dismissUntil == "":
            continue
        _alerts_dto.append(alert)
    print(
        f"Filtered out alerts with empty dismissUntil field. {len(_alerts_dto)} alerts left"
    )
    alerts_dto = _alerts_dto

    # Sort by timestamp desc:
    alerts_dto = sorted(alerts_dto, key=lambda x: x.lastReceived, reverse=False)
    # Take only the first one for each fingerprint:
    alerts_dto = {alert.fingerprint: alert for alert in alerts_dto}.values()
    print(f"Filtered out duplicate alerts. {len(alerts_dto)} alerts left")
    # elastic_client.create_index(tenant_id=TENANT_ID)
    elastic_client.index_alerts(alerts_dto)
    print("Done")
