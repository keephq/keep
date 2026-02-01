# builtins
import dataclasses
import datetime
from collections import defaultdict

import pydantic

# third-parties
from quickchart import QuickChart

# internals
from keep.api.core.db import get_alerts_by_fingerprint
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


def get_date_key(date: datetime.datetime, time_unit: str) -> str:
    if isinstance(date, str):
        date = datetime.datetime.fromisoformat(date)
    if time_unit == "Minutes":
        return f"{date.hour}:{date.minute}:{date.second}"
    elif time_unit == "Hours":
        return f"{date.hour}:{date.minute}"
    else:
        return f"{date.day}/{date.month}/{date.year}"


@pydantic.dataclasses.dataclass
class QuickchartProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Quickchart API Key",
            "sensitive": True,
        },
        default=None,
    )


class QuickchartProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "QuickChart"
    PROVIDER_CATEGORY = ["Developer Tools"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = QuickchartProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _notify(
        self,
        fingerprint: str,
        status: str | None = None,
        chartConfig: dict | None = None,
    ) -> dict:
        db_alerts = get_alerts_by_fingerprint(
            tenant_id=self.context_manager.tenant_id,
            fingerprint=fingerprint,
            limit=False,
            status=status,
        )
        alerts = convert_db_alerts_to_dto_alerts(db_alerts)

        if not alerts:
            self.logger.warning(
                "No alerts found for this fingerprint",
                extra={
                    "tenant_id": self.context_manager.tenant_id,
                    "fingerprint": fingerprint,
                },
            )
            return {"chart_url": ""}

        min_last_received = min(
            datetime.datetime.fromisoformat(alert.lastReceived) for alert in alerts
        )
        max_last_received = max(
            datetime.datetime.fromisoformat(alert.lastReceived) for alert in alerts
        )

        title = f"First: {str(min_last_received)} | Last: {str(max_last_received)} | Total: {len(alerts)}"

        time_difference = (
            max_last_received - min_last_received
        ).total_seconds() * 1000  # Convert to milliseconds
        time_unit = "Days"
        if time_difference < 3600000:
            time_unit = "Minutes"
        elif time_difference < 86400000:
            time_unit = "Hours"

        categories_by_status = []
        raw_chart_data = defaultdict(dict)

        for alert in reversed(alerts):
            date_key = get_date_key(alert.lastReceived, time_unit)
            status = alert.status
            if date_key not in raw_chart_data:
                raw_chart_data[date_key][status] = 1
            else:
                raw_chart_data[date_key][status] = (
                    raw_chart_data[date_key].get(status, 0) + 1
                )

            if status not in categories_by_status:
                categories_by_status.append(status)

        chart_data = [{"date": key, **value} for key, value in raw_chart_data.items()]

        # Generate chart using QuickChart
        return self.generate_chart_image(
            chart_data, categories_by_status, len(alerts), title, chartConfig
        )

    def __get_total_alerts_gaugae(self, counter: int):
        qc = QuickChart()
        if self.authentication_config.api_key:
            qc.key = self.authentication_config.api_key
        qc.width = 500
        qc.height = 300
        qc.config = {
            "type": "radialGauge",
            "data": {"datasets": [{"data": [counter]}]},
            "options": {
                "centerArea": {"fontSize": 25, "fontWeight": "bold"},
            },
        }
        chart_url = qc.get_short_url()
        return chart_url

    def generate_chart_image(
        self,
        chart_data,
        categories_by_status,
        total_alerts: int,
        title: str,
        config: dict | None = None,
    ) -> dict:
        qc = QuickChart()

        if self.authentication_config.api_key:
            qc.key = self.authentication_config.api_key

        qc.width = 800
        qc.height = 400
        qc.config = config or {
            "type": "line",
            "data": {
                "labels": [data["date"] for data in chart_data],
                "datasets": [
                    {
                        "fill": False,
                        "label": category,
                        "lineTension": 0.4,
                        "borderWidth": 3,
                        "data": [data.get(category, 0) for data in chart_data],
                    }
                    for category in categories_by_status
                ],
            },
            "options": {
                "title": {
                    "display": True,
                    "position": "top",
                    "fontSize": 14,
                    "padding": 10,
                    "text": title,
                },
                "scales": {
                    "xAxes": [{"type": "category"}],
                    "yAxes": [{"ticks": {"beginAtZero": True}}],
                },
            },
        }
        chart_url = qc.get_short_url()

        counter_url = self.__get_total_alerts_gaugae(total_alerts)

        return {"chart_url": chart_url, "counter_url": counter_url}


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="keep",
        workflow_id="test",
    )
    config = {
        "description": "",
        "authentication": {},
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="quickchart",
        provider_type="quickchart",
        provider_config=config,
    )
    result = provider.notify(
        fingerprint="5bcafb4ea94749f36871a2e1169d5252ecfb1c589d7464bd8bf863cdeb76b864"
    )
    print(result)
