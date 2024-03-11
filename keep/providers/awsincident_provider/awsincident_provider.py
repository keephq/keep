import boto3
import logging
from typing import Dict, Any, Optional
import pydantic
import dataclasses
from datetime import datetime

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.contextmanager.contextmanager import ContextManager

logger = logging.getLogger(__name__)

@pydantic.dataclasses.dataclass
class AWSIncidentManagerProviderAuthConfig:
    incident_routing_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Optional incident routing key (required for creating incidents)",
        }
    )

class AWSIncidentManagerProvider(BaseProvider):
    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.auth_config = AWSIncidentManagerProviderAuthConfig(**config.authentication)
        self.incident_manager_client = boto3.client('ssm-incidents', region_name=self.config.region)

    def create_incident(self, incident_details: Dict[str, Any]) -> str:
        start_incident_params = {
            'responsePlanArn': incident_details['responsePlanArn'],
            'title': incident_details['title'],
            'triggerDetails': {
                'source': incident_details['source'],
                'timestamp': datetime.now(),
                'triggerArn': incident_details['triggerArn']
            }
        }
        if 'impact' in incident_details:
            start_incident_params['impact'] = incident_details['impact']
        if 'relatedItems' in incident_details:
            start_incident_params['relatedItems'] = incident_details['relatedItems']

        response = self.incident_manager_client.start_incident(**start_incident_params)
        incident_arn = response['incidentRecordArn']
        logger.info(f"Incident created. ARN: {incident_arn}")
        return incident_arn

    def resolve_incident(self, incident_arn: str):
        self.incident_manager_client.update_incident_record(
            Arn=incident_arn,
            Status='RESOLVED'
        )
        logger.info(f"Incident resolved. ARN: {incident_arn}")


if __name__ == "__main__":
    context_manager = ContextManager(tenant_id="example-tenant", workflow_id="example-workflow")
    config = ProviderConfig(region="us-west-2", authentication={"incident_routing_key": "example-routing-key"})
    provider = AWSIncidentManagerProvider(context_manager, "incident-manager-provider-id", config)

    incident_details = {
        "responsePlanArn": "arn:aws:ssm-incidents:us-west-2:123456789012:response-plan/example-response-plan",
        "title": "Example Incident",
        "source": "aws.cloudwatch",
        "triggerArn": "arn:aws:cloudwatch:us-west-2:123456789012:alarm:example-alarm"
    }
    incident_arn = provider.create_incident(incident_details)
    print(f"Incident ARN: {incident_arn}")

    # Resolve the incident
    provider.resolve_incident(incident_arn)
