# Description: Script to migrate data from the database to ElasticSearch
from dotenv import load_dotenv

from keep.api.core.db import get_alerts_with_filters
from keep.api.core.elastic import ElasticClient
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts

load_dotenv()
TENANT_ID = "keep"

if __name__ == "__main__":
    elastic_client = ElasticClient(TENANT_ID)
    alerts = get_alerts_with_filters(TENANT_ID, time_delta=365)  # year ago
    print(f"Found {len(alerts)} alerts")
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    print(f"Converted {len(alerts_dto)} alerts")
    elastic_client.index_alerts(alerts_dto)
    print("Done")
