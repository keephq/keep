"""
AwsEcsProvider is a class that provides a way to interact with AWS ECS clusters,
tasks, services, and ALB (Application Load Balancer) resources.
"""

import dataclasses
import logging
import os

import boto3
import pydantic
from botocore.exceptions import ClientError, NoCredentialsError

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod


@pydantic.dataclasses.dataclass
class AwsEcsProviderAuthConfig:
    """AWS ECS authentication configuration."""

    region: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS region (e.g. us-east-1)",
            "sensitive": False,
            "hint": "e.g. us-east-1",
        }
    )

    access_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS access key ID (leave empty when using IAM role)",
            "sensitive": True,
        },
    )

    secret_access_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS secret access key (leave empty when using IAM role)",
            "sensitive": True,
        },
    )

    session_token: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS session token (for temporary credentials only)",
            "sensitive": True,
        },
    )


class AwsEcsProvider(BaseProvider):
    """Interact with AWS ECS clusters, services, tasks, and ALB resources."""

    PROVIDER_DISPLAY_NAME = "AWS ECS"
    PROVIDER_CATEGORY = ["Cloud Infrastructure", "Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="ecs:ListClusters",
            description="List available ECS clusters",
            documentation_url="https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_ListClusters.html",
            mandatory=True,
            alias="List ECS Clusters",
        ),
        ProviderScope(
            name="ecs:DescribeClusters",
            description="Describe ECS cluster details",
            documentation_url="https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_DescribeClusters.html",
            mandatory=True,
            alias="Describe ECS Clusters",
        ),
        ProviderScope(
            name="ecs:ListServices",
            description="List ECS services in a cluster",
            documentation_url="https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_ListServices.html",
            mandatory=False,
            alias="List ECS Services",
        ),
        ProviderScope(
            name="ecs:DescribeServices",
            description="Describe ECS service details",
            documentation_url="https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_DescribeServices.html",
            mandatory=False,
            alias="Describe ECS Services",
        ),
        ProviderScope(
            name="ecs:ListTasks",
            description="List running ECS tasks",
            documentation_url="https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_ListTasks.html",
            mandatory=False,
            alias="List ECS Tasks",
        ),
        ProviderScope(
            name="ecs:DescribeTasks",
            description="Describe ECS task details",
            documentation_url="https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_DescribeTasks.html",
            mandatory=False,
            alias="Describe ECS Tasks",
        ),
        ProviderScope(
            name="elasticloadbalancing:DescribeLoadBalancers",
            description="List ALB load balancers",
            documentation_url="https://docs.aws.amazon.com/elasticloadbalancing/latest/APIReference/API_DescribeLoadBalancers.html",
            mandatory=False,
            alias="List ALBs",
        ),
        ProviderScope(
            name="elasticloadbalancing:DescribeTargetGroups",
            description="Describe ALB target groups",
            documentation_url="https://docs.aws.amazon.com/elasticloadbalancing/latest/APIReference/API_DescribeTargetGroups.html",
            mandatory=False,
            alias="Describe ALB Target Groups",
        ),
        ProviderScope(
            name="elasticloadbalancing:DescribeListeners",
            description="Describe ALB listeners",
            documentation_url="https://docs.aws.amazon.com/elasticloadbalancing/latest/APIReference/API_DescribeListeners.html",
            mandatory=False,
            alias="Describe ALB Listeners",
        ),
        ProviderScope(
            name="elasticloadbalancing:DescribeTargetHealth",
            description="Describe ALB target health",
            documentation_url="https://docs.aws.amazon.com/elasticloadbalancing/latest/APIReference/API_DescribeTargetHealth.html",
            mandatory=False,
            alias="Describe ALB Target Health",
        ),
    ]

    PROVIDER_METHODS = [
        ProviderMethod(
            name="List Clusters",
            func_name="list_clusters",
            scopes=["ecs:ListClusters", "ecs:DescribeClusters"],
            description="List all ECS clusters in the configured region",
            type="view",
        ),
        ProviderMethod(
            name="List Services",
            func_name="list_services",
            scopes=["ecs:ListServices", "ecs:DescribeServices"],
            description="List all services in an ECS cluster",
            type="view",
        ),
        ProviderMethod(
            name="List Tasks",
            func_name="list_tasks",
            scopes=["ecs:ListTasks", "ecs:DescribeTasks"],
            description="List running tasks in an ECS cluster or service",
            type="view",
        ),
        ProviderMethod(
            name="List Load Balancers",
            func_name="list_load_balancers",
            scopes=["elasticloadbalancing:DescribeLoadBalancers"],
            description="List all Application/Network Load Balancers in the region",
            type="view",
        ),
        ProviderMethod(
            name="Describe Load Balancer",
            func_name="describe_load_balancer",
            scopes=[
                "elasticloadbalancing:DescribeLoadBalancers",
                "elasticloadbalancing:DescribeListeners",
                "elasticloadbalancing:DescribeTargetGroups",
                "elasticloadbalancing:DescribeTargetHealth",
            ],
            description="Get detailed info for a specific ALB including listeners, target groups, and health",
            type="view",
        ),
        ProviderMethod(
            name="Stop Task",
            func_name="stop_task",
            scopes=["ecs:StopTask"],
            description="Stop a running ECS task",
            type="action",
        ),
        ProviderMethod(
            name="Update Service",
            func_name="update_service",
            scopes=["ecs:UpdateService"],
            description="Update an ECS service (e.g. change desired count or force new deployment)",
            type="action",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._ecs_client = None
        self._elbv2_client = None

    def dispose(self):
        """Clean up resources."""
        pass

    def validate_config(self):
        """Validate the provided configuration."""
        self.authentication_config = AwsEcsProviderAuthConfig(
            **self.config.authentication
        )

    # ------------------------------------------------------------------
    # Internal boto3 client helpers
    # ------------------------------------------------------------------

    def _get_ecs_client(self):
        if self._ecs_client is None:
            self._ecs_client = boto3.client(
                "ecs",
                region_name=self.authentication_config.region,
                aws_access_key_id=self.authentication_config.access_key or None,
                aws_secret_access_key=self.authentication_config.secret_access_key
                or None,
                aws_session_token=self.authentication_config.session_token or None,
            )
        return self._ecs_client

    def _get_elbv2_client(self):
        if self._elbv2_client is None:
            self._elbv2_client = boto3.client(
                "elbv2",
                region_name=self.authentication_config.region,
                aws_access_key_id=self.authentication_config.access_key or None,
                aws_secret_access_key=self.authentication_config.secret_access_key
                or None,
                aws_session_token=self.authentication_config.session_token or None,
            )
        return self._elbv2_client

    # ------------------------------------------------------------------
    # Scope validation
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate whether the credentials have the required IAM permissions."""
        scopes: dict[str, bool | str] = {s.name: False for s in self.PROVIDER_SCOPES}

        ecs = self._get_ecs_client()
        elb = self._get_elbv2_client()

        # ecs:ListClusters
        try:
            ecs.list_clusters(maxResults=1)
            scopes["ecs:ListClusters"] = True
        except (ClientError, NoCredentialsError) as exc:
            scopes["ecs:ListClusters"] = str(exc)

        # ecs:DescribeClusters — requires at least one cluster ARN
        try:
            arns = ecs.list_clusters(maxResults=1).get("clusterArns", [])
            if arns:
                ecs.describe_clusters(clusters=[arns[0]])
            scopes["ecs:DescribeClusters"] = True
        except (ClientError, NoCredentialsError) as exc:
            scopes["ecs:DescribeClusters"] = str(exc)

        # ecs:ListServices
        try:
            arns = ecs.list_clusters(maxResults=1).get("clusterArns", [])
            if arns:
                ecs.list_services(cluster=arns[0], maxResults=1)
            scopes["ecs:ListServices"] = True
        except (ClientError, NoCredentialsError) as exc:
            scopes["ecs:ListServices"] = str(exc)

        # ecs:DescribeServices
        try:
            arns = ecs.list_clusters(maxResults=1).get("clusterArns", [])
            if arns:
                svc_arns = ecs.list_services(
                    cluster=arns[0], maxResults=1
                ).get("serviceArns", [])
                if svc_arns:
                    ecs.describe_services(cluster=arns[0], services=[svc_arns[0]])
            scopes["ecs:DescribeServices"] = True
        except (ClientError, NoCredentialsError) as exc:
            scopes["ecs:DescribeServices"] = str(exc)

        # ecs:ListTasks
        try:
            arns = ecs.list_clusters(maxResults=1).get("clusterArns", [])
            if arns:
                ecs.list_tasks(cluster=arns[0], maxResults=1)
            scopes["ecs:ListTasks"] = True
        except (ClientError, NoCredentialsError) as exc:
            scopes["ecs:ListTasks"] = str(exc)

        # ecs:DescribeTasks
        try:
            arns = ecs.list_clusters(maxResults=1).get("clusterArns", [])
            if arns:
                task_arns = ecs.list_tasks(
                    cluster=arns[0], maxResults=1
                ).get("taskArns", [])
                if task_arns:
                    ecs.describe_tasks(cluster=arns[0], tasks=[task_arns[0]])
            scopes["ecs:DescribeTasks"] = True
        except (ClientError, NoCredentialsError) as exc:
            scopes["ecs:DescribeTasks"] = str(exc)

        # ELB scopes
        try:
            elb.describe_load_balancers(PageSize=1)
            scopes["elasticloadbalancing:DescribeLoadBalancers"] = True
        except (ClientError, NoCredentialsError) as exc:
            scopes["elasticloadbalancing:DescribeLoadBalancers"] = str(exc)

        try:
            elb.describe_target_groups(PageSize=1)
            scopes["elasticloadbalancing:DescribeTargetGroups"] = True
        except (ClientError, NoCredentialsError) as exc:
            scopes["elasticloadbalancing:DescribeTargetGroups"] = str(exc)

        try:
            lbs = elb.describe_load_balancers(PageSize=1).get("LoadBalancers", [])
            if lbs:
                elb.describe_listeners(
                    LoadBalancerArn=lbs[0]["LoadBalancerArn"], PageSize=1
                )
            scopes["elasticloadbalancing:DescribeListeners"] = True
        except (ClientError, NoCredentialsError) as exc:
            scopes["elasticloadbalancing:DescribeListeners"] = str(exc)

        try:
            tgs = elb.describe_target_groups(PageSize=1).get("TargetGroups", [])
            if tgs:
                elb.describe_target_health(
                    TargetGroupArn=tgs[0]["TargetGroupArn"]
                )
            scopes["elasticloadbalancing:DescribeTargetHealth"] = True
        except (ClientError, NoCredentialsError) as exc:
            scopes["elasticloadbalancing:DescribeTargetHealth"] = str(exc)

        return scopes

    # ------------------------------------------------------------------
    # ECS — cluster, service, task helpers
    # ------------------------------------------------------------------

    def list_clusters(self) -> list[dict]:
        """
        Return all ECS clusters in the configured region with their details.
        """
        ecs = self._get_ecs_client()
        cluster_arns: list[str] = []
        paginator = ecs.get_paginator("list_clusters")
        for page in paginator.paginate():
            cluster_arns.extend(page.get("clusterArns", []))

        if not cluster_arns:
            return []

        result = []
        # describe_clusters accepts at most 100 ARNs at a time
        for i in range(0, len(cluster_arns), 100):
            batch = cluster_arns[i : i + 100]
            resp = ecs.describe_clusters(clusters=batch, include=["STATISTICS", "TAGS"])
            result.extend(resp.get("clusters", []))

        self.logger.info(f"Found {len(result)} ECS clusters")
        return result

    def list_services(self, cluster: str) -> list[dict]:
        """
        Return all ECS services in *cluster* with their details.

        Args:
            cluster: Cluster name or full ARN.
        """
        if not cluster:
            raise ProviderException("cluster is required for list_services")

        ecs = self._get_ecs_client()
        svc_arns: list[str] = []
        paginator = ecs.get_paginator("list_services")
        for page in paginator.paginate(cluster=cluster):
            svc_arns.extend(page.get("serviceArns", []))

        if not svc_arns:
            return []

        result = []
        for i in range(0, len(svc_arns), 10):  # describe_services max 10
            batch = svc_arns[i : i + 10]
            resp = ecs.describe_services(cluster=cluster, services=batch)
            result.extend(resp.get("services", []))

        self.logger.info(f"Found {len(result)} services in cluster {cluster}")
        return result

    def list_tasks(
        self,
        cluster: str,
        service: str = None,
        desired_status: str = "RUNNING",
    ) -> list[dict]:
        """
        Return tasks in *cluster*, optionally filtered by *service*.

        Args:
            cluster: Cluster name or ARN.
            service: Service name or ARN (optional).
            desired_status: One of RUNNING, PENDING, STOPPED (default RUNNING).
        """
        if not cluster:
            raise ProviderException("cluster is required for list_tasks")

        ecs = self._get_ecs_client()
        task_arns: list[str] = []
        kwargs: dict = {"cluster": cluster, "desiredStatus": desired_status}
        if service:
            kwargs["serviceName"] = service

        paginator = ecs.get_paginator("list_tasks")
        for page in paginator.paginate(**kwargs):
            task_arns.extend(page.get("taskArns", []))

        if not task_arns:
            return []

        result = []
        for i in range(0, len(task_arns), 100):  # describe_tasks max 100
            batch = task_arns[i : i + 100]
            resp = ecs.describe_tasks(cluster=cluster, tasks=batch, include=["TAGS"])
            result.extend(resp.get("tasks", []))

        self.logger.info(
            f"Found {len(result)} {desired_status} tasks in cluster {cluster}"
        )
        return result

    def stop_task(self, cluster: str, task: str, reason: str = "Stopped by Keep") -> dict:
        """
        Stop a running ECS task.

        Args:
            cluster: Cluster name or ARN.
            task: Task ID or ARN.
            reason: Human-readable reason (shown in ECS console).
        """
        if not cluster or not task:
            raise ProviderException("cluster and task are required for stop_task")

        ecs = self._get_ecs_client()
        self.logger.info(f"Stopping task {task} in cluster {cluster}")
        resp = ecs.stop_task(cluster=cluster, task=task, reason=reason)
        return resp.get("task", {})

    def update_service(
        self,
        cluster: str,
        service: str,
        desired_count: int = None,
        force_new_deployment: bool = False,
    ) -> dict:
        """
        Update an ECS service.

        Args:
            cluster: Cluster name or ARN.
            service: Service name or ARN.
            desired_count: New desired task count (None = keep existing).
            force_new_deployment: Force a new deployment (rolls tasks with latest image).
        """
        if not cluster or not service:
            raise ProviderException("cluster and service are required for update_service")

        ecs = self._get_ecs_client()
        kwargs: dict = {
            "cluster": cluster,
            "service": service,
            "forceNewDeployment": force_new_deployment,
        }
        if desired_count is not None:
            kwargs["desiredCount"] = desired_count

        self.logger.info(f"Updating service {service} in cluster {cluster}")
        resp = ecs.update_service(**kwargs)
        return resp.get("service", {})

    # ------------------------------------------------------------------
    # ALB / ELBv2 helpers
    # ------------------------------------------------------------------

    def list_load_balancers(self, lb_type: str = None) -> list[dict]:
        """
        Return all load balancers in the region.

        Args:
            lb_type: Filter by type: 'application', 'network', or 'gateway'.
                     Leave None to return all types.
        """
        elb = self._get_elbv2_client()
        result: list[dict] = []
        paginator = elb.get_paginator("describe_load_balancers")
        for page in paginator.paginate():
            for lb in page.get("LoadBalancers", []):
                if lb_type is None or lb.get("Type", "").lower() == lb_type.lower():
                    result.append(lb)

        self.logger.info(f"Found {len(result)} load balancers")
        return result

    def describe_load_balancer(self, load_balancer_arn: str) -> dict:
        """
        Return full detail for a specific ALB: listeners, rules, target groups,
        and target health.

        Args:
            load_balancer_arn: Full ARN of the load balancer.
        """
        if not load_balancer_arn:
            raise ProviderException(
                "load_balancer_arn is required for describe_load_balancer"
            )

        elb = self._get_elbv2_client()

        # Basic LB info
        lb_resp = elb.describe_load_balancers(LoadBalancerArns=[load_balancer_arn])
        lbs = lb_resp.get("LoadBalancers", [])
        if not lbs:
            raise ProviderException(
                f"Load balancer not found: {load_balancer_arn}"
            )
        lb_info = lbs[0]

        # Listeners
        listeners: list[dict] = []
        paginator = elb.get_paginator("describe_listeners")
        for page in paginator.paginate(LoadBalancerArn=load_balancer_arn):
            listeners.extend(page.get("Listeners", []))

        # Target groups
        tg_resp = elb.describe_target_groups(LoadBalancerArn=load_balancer_arn)
        target_groups: list[dict] = tg_resp.get("TargetGroups", [])

        # Target health for each TG
        for tg in target_groups:
            try:
                health_resp = elb.describe_target_health(
                    TargetGroupArn=tg["TargetGroupArn"]
                )
                tg["TargetHealthDescriptions"] = health_resp.get(
                    "TargetHealthDescriptions", []
                )
            except ClientError as exc:
                self.logger.warning(
                    f"Could not describe target health for {tg.get('TargetGroupName')}: {exc}"
                )
                tg["TargetHealthDescriptions"] = []

        return {
            "LoadBalancer": lb_info,
            "Listeners": listeners,
            "TargetGroups": target_groups,
        }

    # ------------------------------------------------------------------
    # _query dispatcher (required by BaseProvider)
    # ------------------------------------------------------------------

    def _query(self, command_type: str, **kwargs: dict):
        """
        Dispatch a query to the appropriate provider method.

        Args:
            command_type: One of the method names defined in PROVIDER_METHODS.
            **kwargs: Arguments forwarded to the method.
        """
        dispatch = {
            "list_clusters": self.list_clusters,
            "list_services": self.list_services,
            "list_tasks": self.list_tasks,
            "list_load_balancers": self.list_load_balancers,
            "describe_load_balancer": self.describe_load_balancer,
            "stop_task": self.stop_task,
            "update_service": self.update_service,
        }
        if command_type not in dispatch:
            raise NotImplementedError(
                f"Command type '{command_type}' not implemented. "
                f"Available: {list(dispatch)}"
            )
        return dispatch[command_type](**kwargs)


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        authentication={
            "region": os.environ.get("AWS_REGION") or "us-east-1",
            "access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
            "secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        }
    )

    provider = AwsEcsProvider(context_manager, "awsecs-demo", config)

    print("Validating scopes...")
    scopes = provider.validate_scopes()
    for scope, ok in scopes.items():
        print(f"  {scope}: {ok}")

    print("\nListing clusters...")
    clusters = provider.list_clusters()
    for c in clusters:
        print(f"  {c.get('clusterName')} — {c.get('status')}")

    if clusters:
        cluster_arn = clusters[0]["clusterArn"]
        print(f"\nListing services in {cluster_arn}...")
        services = provider.list_services(cluster=cluster_arn)
        for svc in services[:5]:
            print(
                f"  {svc.get('serviceName')} — desired:{svc.get('desiredCount')} "
                f"running:{svc.get('runningCount')}"
            )

        print(f"\nListing running tasks in {cluster_arn}...")
        tasks = provider.list_tasks(cluster=cluster_arn)
        for t in tasks[:5]:
            print(f"  {t.get('taskArn','').split('/')[-1]} — {t.get('lastStatus')}")

    print("\nListing load balancers...")
    lbs = provider.list_load_balancers()
    for lb in lbs[:5]:
        print(f"  {lb.get('LoadBalancerName')} — {lb.get('Type')} — {lb.get('State',{}).get('Code')}")
