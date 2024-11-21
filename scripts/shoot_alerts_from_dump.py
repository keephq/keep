import sys
import json
import copy
import csv
import logging
import argparse

from keep.api.core.db import get_session_sync
from keep.api.models.alert import AlertDto
from keep.api.tasks.process_event_task import __handle_formatted_events


# configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def count_alerts_for_tenants(csv_file):
    tenants = {}
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        progress = 0
        for row in reader:
            progress += 1
            if progress % 10000 == 0:
                print(f"Processing row {progress}")
            if len(row) > 2:
                tenants[row[2]] = tenants.get(row[2], 0) + 1
    print("Tenants and their alerts count:")
    print({k: v for k, v in sorted(tenants.items(),
          key=lambda item: item[1], reverse=True)})


def shoot_tenants_alerts(file, tenant_id):
    new_tenant_id = "keep"
    session = get_session_sync()
    with open(file, 'r') as file:
        reader = csv.reader(file)
        file.seek(0)

        for row in reader:
            if len(row) > 2 and row[2] == tenant_id:
                alert = json.loads(row[0])
                alert["tenant_id"] = new_tenant_id
                raw_event = [copy.deepcopy(alert)]
                alert = AlertDto(**alert)
                __handle_formatted_events(
                    new_tenant_id,
                    provider_type=row[2],
                    session=session,
                    raw_events=raw_event,
                    formatted_events=[alert],
                    timestamp_forced=alert.lastReceived
                )
    session.close()


def shoot_tenants_alerts_from_json(file):
    new_tenant_id = "keep"
    session = get_session_sync()
    with open(file, 'r') as file:
        dict = json.load(file)
        for row in dict:
            if 'incident' in row['event']:
                pass

            alert = json.loads(row['event'])
            alert["tenant_id"] = new_tenant_id
            raw_event = [copy.deepcopy(alert)]
            alert = AlertDto(**alert)
            __handle_formatted_events(
                new_tenant_id,
                provider_type=row['provider_type'],
                session=session,
                raw_events=raw_event,
                formatted_events=[alert],
                timestamp_forced=alert.lastReceived
            )
    session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shoot alerts from dump")
    parser.add_argument(
        "--csv_file", help="Path to the CSV file", default=None)
    parser.add_argument(
        "--tenant-id", help="ID of the tenant, if no tenant_id is provided, listing tenants.", default=None)
    parser.add_argument(
        "--json", help="JSON dump file for a single tenant", default=None)

    args = parser.parse_args()

    csv_file = args.csv_file
    tenant_id = args.tenant_id
    json_file = args.json

    if csv_file:
        csv.field_size_limit(sys.maxsize)

        if tenant_id is None:
            count_alerts_for_tenants(csv_file)
        else:
            shoot_tenants_alerts(csv_file, tenant_id)

    elif json_file:
        shoot_tenants_alerts_from_json(json_file)
