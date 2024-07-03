# Description: Script to migrate data from the database to ElasticSearch
import os

from dotenv import load_dotenv

from keep.api.core.db import get_alerts_with_filters
from keep.api.core.elastic import ElasticClient
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts

load_dotenv()
TENANT_ID = os.environ.get("MIGRATION_TENANT_ID")

if __name__ == "__main__":
    # dismissedUntil + group last_updated_time + split to 500
    elastic_client = ElasticClient()
    alerts = get_alerts_with_filters(TENANT_ID, time_delta=365)  # year ago
    print(f"Found {len(alerts)} alerts")
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    print(f"Converted {len(alerts_dto)} alerts")
    # sort by timestamp desc:
    alerts_dto = sorted(alerts_dto, key=lambda x: x.lastReceived, reverse=True)
    # take only the first one for each fingerprint:
    alerts_dto = {alert.fingerprint: alert for alert in alerts_dto}.values()
    elastic_client.index_alerts(TENANT_ID, alerts_dto)
    print("Done")
