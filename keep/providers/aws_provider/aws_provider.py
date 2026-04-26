"""
AwsProvider is a class that allows querying AWS resources including ECS clusters,
tasks, ALB (Application Load Balancers), and other infrastructure components.
"""

import dataclasses
import logging
from typing import Any, Optional

import boto3
import botocore.exceptions
import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class AwsProviderAuthConfig:
    """
    AWS authentication configuration.

    Credentials are optional when running on an EC2 instance or ECS task
    with an IAM role attached — boto3 will pick them up automatically.
    """

    region: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS region",
            "hint": "e.g. us-east-1",
            "sensitive": False,
        },
    )
    access_key_id: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS Access Key ID",
            "hint": "Leave empty to use the instance/task IAM role",
            "sensitive": False,
        },
    )
    secret_access_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS Secret Access Key",
            "sensitive": True,
        },
    )
    session_token: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS Session Token (for temporary credentials)",
            "sensitive": True,
        },
    )


class AwsProvider(BaseProvider):
    """Query AWS resources: ECS clusters/tasks, ALBs, EC2 instances, and more."""

    PROVIDER_DISPLAY_NAME = "AWS"
    PROVIDER_CATEGORY = ["Cloud Infrastructure"]
    PROVIDER_TAGS = ["cloud", "aws", "infrastructure"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="ecs:ListClusters",
            description="List ECS clusters.",
            mandatory=False,
            alias="ECS List Clusters",
        ),
        ProviderScope(
            name="ecs:DescribeClusters",
            description="Describe ECS clusters.",
            mandatory=False,
            alias="ECS Describe Clusters",
        ),
        ProviderScope(
            name="ecs:ListTasks",
            description="List ECS tasks.",
            mandatory=False,
            alias="ECS List Tasks",
        ),
        ProviderScope(
            name="ecs:DescribeTasks",
            description="Describe ECS tasks.",
            mandatory=False,
            alias="ECS Describe Tasks",
        ),
        ProviderScope(
            name="elasticloadbalancing:DescribeLoadBalancers",
            description="Describe Application/Network Load Balancers.",
            mandatory=False,
            alias="ELB Describe Load Balancers",
        ),
        ProviderScope(
            name="elasticloadbalancing:DescribeTargetGroups",
            description="Describe ALB target groups.",
            mandatory=False,
            alias="ELB Describe Target Groups",
        ),
        ProviderScope(
            name="ec2:DescribeInstances",
            description="Describe EC2 instances.",
            mandatory=False,
            alias="EC2 Describe Instances",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self._session: Optional[boto3.Session] = None

    def validate_config(self):
        self.authentication_config = AwsProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _get_session(self) -> boto3.Session:
        if self._session is None:
            kwargs: dict[str, Any] = {
                "region_name": self.authentication_config.region,
            }
            if self.authentication_config.access_key_id:
                kwargs["aws_access_key_id"] = self.authentication_config.access_key_id
            if self.authentication_config.secret_access_key:
                kwargs["aws_secret_access_key"] = (
                    self.authentication_config.secret_access_key
                )
            if self.authentication_config.session_token:
                kwargs["aws_session_token"] = self.authentication_config.session_token
            self._session = boto3.Session(**kwargs)
        return self._session

    def _client(self, service: str):
        return self._get_session().client(service)

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes: dict[str, bool | str] = {}
        session = self._get_session()

        # ECS checks
        try:
            ecs = session.client("ecs")
            ecs.list_clusters(maxResults=1)
            scopes["ecs:ListClusters"] = True
            try:
                resp = ecs.list_clusters(maxResults=1)
                arns = resp.get("clusterArns", [])
                if arns:
                    ecs.describe_clusters(clusters=[arns[0]])
                scopes["ecs:DescribeClusters"] = True
            except botocore.exceptions.ClientError as e:
                scopes["ecs:DescribeClusters"] = str(e)
            try:
                ecs.list_tasks(maxResults=1)
                scopes["ecs:ListTasks"] = True
            except botocore.exceptions.ClientError as e:
                scopes["ecs:ListTasks"] = str(e)
        except botocore.exceptions.ClientError as e:
            scopes["ecs:ListClusters"] = str(e)
            scopes["ecs:DescribeClusters"] = str(e)
            scopes["ecs:ListTasks"] = str(e)

        # ALB checks
        try:
            elb = session.client("elbv2")
            elb.describe_load_balancers(PageSize=1)
            scopes["elasticloadbalancing:DescribeLoadBalancers"] = True
            try:
                elb.describe_target_groups(PageSize=1)
                scopes["elasticloadbalancing:DescribeTargetGroups"] = True
            except botocore.exceptions.ClientError as e:
                scopes["elasticloadbalancing:DescribeTargetGroups"] = str(e)
        except botocore.exceptions.ClientError as e:
            scopes["elasticloadbalancing:DescribeLoadBalancers"] = str(e)
            scopes["elasticloadbalancing:DescribeTargetGroups"] = str(e)

        # EC2 checks
        try:
            ec2 = session.client("ec2")
            ec2.describe_instances(MaxResults=5)
            scopes["ec2:DescribeInstances"] = True
        except botocore.exceptions.ClientError as e:
            scopes["ec2:DescribeInstances"] = str(e)

        return scopes

    # ------------------------------------------------------------------
    # ECS helpers
    # ------------------------------------------------------------------

    def _describe_ecs_clusters(self, cluster_arns: Optional[list] = None) -> list:
        """Return details for ECS clusters."""
        ecs = self._client("ecs")
        if not cluster_arns:
            paginator = ecs.get_paginator("list_clusters")
            cluster_arns = []
            for page in paginator.paginate():
                cluster_arns.extend(page.get("clusterArns", []))
        if not cluster_arns:
            return []
        # describe_clusters accepts at most 100 at a time
        results = []
        for i in range(0, len(cluster_arns), 100):
            resp = ecs.describe_clusters(clusters=cluster_arns[i : i + 100])
            results.extend(resp.get("clusters", []))
        return results

    def _describe_ecs_tasks(
        self,
        cluster: Optional[str] = None,
        desired_status: Optional[str] = None,
    ) -> list:
        """Return ECS task details for a cluster (or all clusters)."""
        ecs = self._client("ecs")
        if cluster:
            cluster_arns = [cluster]
        else:
            paginator = ecs.get_paginator("list_clusters")
            cluster_arns = []
            for page in paginator.paginate():
                cluster_arns.extend(page.get("clusterArns", []))

        tasks: list = []
        for c_arn in cluster_arns:
            list_kwargs: dict[str, Any] = {"cluster": c_arn}
            if desired_status:
                list_kwargs["desiredStatus"] = desired_status.upper()
            paginator = ecs.get_paginator("list_tasks")
            task_arns = []
            for page in paginator.paginate(**list_kwargs):
                task_arns.extend(page.get("taskArns", []))
            for i in range(0, len(task_arns), 100):
                resp = ecs.describe_tasks(
                    cluster=c_arn, tasks=task_arns[i : i + 100]
                )
                tasks.extend(resp.get("tasks", []))
        return tasks

    # ------------------------------------------------------------------
    # ALB helpers
    # ------------------------------------------------------------------

    def _describe_load_balancers(
        self,
        names: Optional[list] = None,
        arns: Optional[list] = None,
    ) -> list:
        """Return Application/Network Load Balancer details."""
        elb = self._client("elbv2")
        kwargs: dict[str, Any] = {}
        if names:
            kwargs["Names"] = names
        if arns:
            kwargs["LoadBalancerArns"] = arns
        paginator = elb.get_paginator("describe_load_balancers")
        lbs: list = []
        for page in paginator.paginate(**kwargs):
            lbs.extend(page.get("LoadBalancers", []))
        return lbs

    def _describe_target_groups(
        self, load_balancer_arn: Optional[str] = None
    ) -> list:
        """Return ALB target groups, optionally filtered by load balancer."""
        elb = self._client("elbv2")
        kwargs: dict[str, Any] = {}
        if load_balancer_arn:
            kwargs["LoadBalancerArn"] = load_balancer_arn
        paginator = elb.get_paginator("describe_target_groups")
        groups: list = []
        for page in paginator.paginate(**kwargs):
            groups.extend(page.get("TargetGroups", []))
        return groups

    # ------------------------------------------------------------------
    # EC2 helpers
    # ------------------------------------------------------------------

    def _describe_ec2_instances(
        self,
        instance_ids: Optional[list] = None,
        filters: Optional[list] = None,
    ) -> list:
        """Return EC2 instance details."""
        ec2 = self._client("ec2")
        kwargs: dict[str, Any] = {}
        if instance_ids:
            kwargs["InstanceIds"] = instance_ids
        if filters:
            kwargs["Filters"] = filters
        paginator = ec2.get_paginator("describe_instances")
        instances: list = []
        for page in paginator.paginate(**kwargs):
            for reservation in page.get("Reservations", []):
                instances.extend(reservation.get("Instances", []))
        return instances

    # ------------------------------------------------------------------
    # BaseProvider query interface
    # ------------------------------------------------------------------

    def _query(
        self,
        resource: str = "ecs_clusters",
        cluster: Optional[str] = None,
        desired_status: Optional[str] = None,
        load_balancer_arn: Optional[str] = None,
        instance_ids: Optional[list] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Query AWS resources.

        Args:
            resource: One of "ecs_clusters", "ecs_tasks", "load_balancers",
                      "target_groups", "ec2_instances".
            cluster: (ecs_tasks) ECS cluster name or ARN to scope the query.
            desired_status: (ecs_tasks) "RUNNING" | "STOPPED" | "PENDING".
            load_balancer_arn: (target_groups) Filter target groups by LB.
            instance_ids: (ec2_instances) Specific instance IDs to describe.

        Returns:
            A dict with a ``results`` key containing the matching resources.
        """
        resource = resource.lower()

        if resource == "ecs_clusters":
            data = self._describe_ecs_clusters()
        elif resource == "ecs_tasks":
            data = self._describe_ecs_tasks(
                cluster=cluster, desired_status=desired_status
            )
        elif resource == "load_balancers":
            data = self._describe_load_balancers()
        elif resource == "target_groups":
            data = self._describe_target_groups(
                load_balancer_arn=load_balancer_arn
            )
        elif resource == "ec2_instances":
            data = self._describe_ec2_instances(instance_ids=instance_ids)
        else:
            raise ValueError(
                f"Unknown resource type '{resource}'. Valid values: "
                "ecs_clusters, ecs_tasks, load_balancers, target_groups, ec2_instances."
            )

        return {"results": data, "resource": resource, "count": len(data)}


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    config = ProviderConfig(
        description="AWS Provider",
        authentication={
            "region": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            "access_key_id": os.environ.get("AWS_ACCESS_KEY_ID"),
            "secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        },
    )
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    provider = AwsProvider(context_manager, provider_id="aws-test", config=config)
    result = provider._query(resource="ecs_clusters")
    print("ECS clusters:", result)
