"""
Unit tests for AwsEcsProvider.

All AWS API calls are mocked — no real credentials or AWS account needed.
"""
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.awsecs_provider.awsecs_provider import (
    AwsEcsProvider,
    AwsEcsProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig
from keep.exceptions.provider_exception import ProviderException


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def context_manager():
    return ContextManager(tenant_id="singletenant", workflow_id="test")


@pytest.fixture
def ecs_config():
    return ProviderConfig(
        authentication={
            "region": "us-east-1",
            "access_key": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        }
    )


@pytest.fixture
def provider(context_manager, ecs_config):
    return AwsEcsProvider(context_manager, "awsecs-test", ecs_config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_ecs(provider, cluster_arns, clusters):
    """Inject a mock ECS boto3 client into *provider*."""
    mc = MagicMock()
    provider._ecs_client = mc
    pag = MagicMock()
    pag.paginate.return_value = [{"clusterArns": cluster_arns}]
    mc.get_paginator.return_value = pag
    mc.describe_clusters.return_value = {"clusters": clusters}
    return mc


def _mock_elb(provider, lbs):
    """Inject a mock ELBv2 boto3 client into *provider*."""
    mc = MagicMock()
    provider._elbv2_client = mc
    pag = MagicMock()
    pag.paginate.return_value = [{"LoadBalancers": lbs}]
    mc.get_paginator.return_value = pag
    return mc


# ===========================================================================
# Config / auth
# ===========================================================================


class TestConfig:
    def test_auth_type(self, provider):
        assert isinstance(provider.authentication_config, AwsEcsProviderAuthConfig)

    def test_region(self, context_manager):
        config = ProviderConfig(
            authentication={"region": "eu-west-1", "access_key": "AK", "secret_access_key": "SK"}
        )
        p = AwsEcsProvider(context_manager, "p", config)
        assert p.authentication_config.region == "eu-west-1"

    def test_optional_default_none(self, context_manager):
        config = ProviderConfig(authentication={"region": "ap-southeast-1"})
        p = AwsEcsProvider(context_manager, "p", config)
        assert p.authentication_config.access_key is None
        assert p.authentication_config.secret_access_key is None
        assert p.authentication_config.session_token is None

    def test_session_token(self, context_manager):
        config = ProviderConfig(authentication={
            "region": "us-west-2",
            "access_key": "AK", "secret_access_key": "SK", "session_token": "TOK"
        })
        p = AwsEcsProvider(context_manager, "p", config)
        assert p.authentication_config.session_token == "TOK"


# ===========================================================================
# list_clusters
# ===========================================================================


class TestListClusters:
    def test_empty_region(self, provider):
        _mock_ecs(provider, [], [])
        assert provider.list_clusters() == []

    def test_single_cluster(self, provider):
        arn = "arn:aws:ecs:us-east-1:123:cluster/c1"
        cluster = {"clusterArn": arn, "clusterName": "c1", "status": "ACTIVE"}
        _mock_ecs(provider, [arn], [cluster])
        result = provider.list_clusters()
        assert len(result) == 1
        assert result[0]["clusterName"] == "c1"

    def test_multiple_clusters(self, provider):
        arns = [f"arn:c{i}" for i in range(3)]
        clusters = [{"clusterArn": a, "clusterName": f"c{i}"} for i, a in enumerate(arns)]
        _mock_ecs(provider, arns, clusters)
        assert len(provider.list_clusters()) == 3

    def test_statistics_tags_included(self, provider):
        mc = _mock_ecs(provider, ["arn:c1"], [])
        provider.list_clusters()
        include = mc.describe_clusters.call_args[1].get("include", [])
        assert "STATISTICS" in include
        assert "TAGS" in include


# ===========================================================================
# list_services
# ===========================================================================


class TestListServices:
    def test_requires_cluster(self, provider):
        with pytest.raises(ProviderException):
            provider.list_services(cluster="")

    def test_empty_cluster(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        pag = MagicMock()
        pag.paginate.return_value = [{"serviceArns": []}]
        mc.get_paginator.return_value = pag
        assert provider.list_services(cluster="c") == []

    def test_two_services(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        arns = ["arn:svc/a", "arn:svc/b"]
        pag = MagicMock()
        pag.paginate.return_value = [{"serviceArns": arns}]
        mc.get_paginator.return_value = pag
        mc.describe_services.return_value = {
            "services": [
                {"serviceArn": arns[0], "serviceName": "a"},
                {"serviceArn": arns[1], "serviceName": "b"},
            ]
        }
        result = provider.list_services(cluster="c")
        assert len(result) == 2

    def test_cluster_passed_to_describe(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        pag = MagicMock()
        pag.paginate.return_value = [{"serviceArns": ["arn:1"]}]
        mc.get_paginator.return_value = pag
        mc.describe_services.return_value = {"services": [{}]}
        provider.list_services(cluster="my-cluster")
        assert mc.describe_services.call_args[1]["cluster"] == "my-cluster"


# ===========================================================================
# list_tasks
# ===========================================================================


class TestListTasks:
    def _pag(self, provider, arns):
        mc = MagicMock()
        provider._ecs_client = mc
        pag = MagicMock()
        pag.paginate.return_value = [{"taskArns": arns}]
        mc.get_paginator.return_value = pag
        return mc, pag

    def test_requires_cluster(self, provider):
        with pytest.raises(ProviderException):
            provider.list_tasks(cluster="")

    def test_no_tasks(self, provider):
        self._pag(provider, [])
        assert provider.list_tasks(cluster="c") == []

    def test_running_tasks(self, provider):
        arns = ["arn:task/a", "arn:task/b"]
        mc, _ = self._pag(provider, arns)
        mc.describe_tasks.return_value = {"tasks": [{"taskArn": a, "lastStatus": "RUNNING"} for a in arns]}
        result = provider.list_tasks(cluster="c")
        assert len(result) == 2
        assert all(t["lastStatus"] == "RUNNING" for t in result)

    def test_service_filter(self, provider):
        _, pag = self._pag(provider, [])
        provider.list_tasks(cluster="c", service="svc-a")
        assert pag.paginate.call_args[1].get("serviceName") == "svc-a"

    def test_default_status_running(self, provider):
        _, pag = self._pag(provider, [])
        provider.list_tasks(cluster="c")
        assert pag.paginate.call_args[1].get("desiredStatus") == "RUNNING"

    def test_custom_status(self, provider):
        _, pag = self._pag(provider, [])
        provider.list_tasks(cluster="c", desired_status="STOPPED")
        assert pag.paginate.call_args[1].get("desiredStatus") == "STOPPED"


# ===========================================================================
# stop_task
# ===========================================================================


class TestStopTask:
    def test_requires_cluster(self, provider):
        with pytest.raises(ProviderException):
            provider.stop_task(cluster="", task="t")

    def test_requires_task(self, provider):
        with pytest.raises(ProviderException):
            provider.stop_task(cluster="c", task="")

    def test_default_reason(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        mc.stop_task.return_value = {"task": {"lastStatus": "STOPPED"}}
        provider.stop_task(cluster="c", task="t")
        mc.stop_task.assert_called_once_with(cluster="c", task="t", reason="Stopped by Keep")

    def test_custom_reason(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        mc.stop_task.return_value = {"task": {}}
        provider.stop_task(cluster="c", task="t", reason="cleanup")
        assert mc.stop_task.call_args[1]["reason"] == "cleanup"

    def test_returns_task(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        mc.stop_task.return_value = {"task": {"lastStatus": "STOPPED"}}
        result = provider.stop_task(cluster="c", task="t")
        assert result["lastStatus"] == "STOPPED"


# ===========================================================================
# update_service
# ===========================================================================


class TestUpdateService:
    def test_requires_cluster(self, provider):
        with pytest.raises(ProviderException):
            provider.update_service(cluster="", service="s")

    def test_requires_service(self, provider):
        with pytest.raises(ProviderException):
            provider.update_service(cluster="c", service="")

    def test_force_new_deployment(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        mc.update_service.return_value = {"service": {}}
        provider.update_service(cluster="c", service="s", force_new_deployment=True)
        assert mc.update_service.call_args[1]["forceNewDeployment"] is True

    def test_desired_count(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        mc.update_service.return_value = {"service": {}}
        provider.update_service(cluster="c", service="s", desired_count=5)
        assert mc.update_service.call_args[1]["desiredCount"] == 5

    def test_desired_count_omitted_when_none(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        mc.update_service.return_value = {"service": {}}
        provider.update_service(cluster="c", service="s")
        assert "desiredCount" not in mc.update_service.call_args[1]

    def test_returns_service(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        mc.update_service.return_value = {"service": {"serviceName": "s", "runningCount": 2}}
        result = provider.update_service(cluster="c", service="s")
        assert result["serviceName"] == "s"


# ===========================================================================
# list_load_balancers
# ===========================================================================


class TestListLoadBalancers:
    def test_empty(self, provider):
        _mock_elb(provider, [])
        assert provider.list_load_balancers() == []

    def test_all_types(self, provider):
        lbs = [{"LoadBalancerName": "a", "Type": "application"}, {"LoadBalancerName": "n", "Type": "network"}]
        _mock_elb(provider, lbs)
        assert len(provider.list_load_balancers()) == 2

    def test_filter_application(self, provider):
        lbs = [{"LoadBalancerName": "a", "Type": "application"}, {"LoadBalancerName": "n", "Type": "network"}]
        _mock_elb(provider, lbs)
        result = provider.list_load_balancers(lb_type="application")
        assert len(result) == 1
        assert result[0]["LoadBalancerName"] == "a"

    def test_filter_case_insensitive(self, provider):
        _mock_elb(provider, [{"LoadBalancerName": "a", "Type": "application"}])
        assert len(provider.list_load_balancers(lb_type="APPLICATION")) == 1

    def test_filter_network(self, provider):
        lbs = [{"LoadBalancerName": "a", "Type": "application"}, {"LoadBalancerName": "n", "Type": "network"}]
        _mock_elb(provider, lbs)
        result = provider.list_load_balancers(lb_type="network")
        assert len(result) == 1
        assert result[0]["LoadBalancerName"] == "n"


# ===========================================================================
# describe_load_balancer
# ===========================================================================


class TestDescribeLoadBalancer:
    def test_requires_arn(self, provider):
        with pytest.raises(ProviderException):
            provider.describe_load_balancer(load_balancer_arn="")

    def test_not_found(self, provider):
        mc = MagicMock()
        provider._elbv2_client = mc
        mc.describe_load_balancers.return_value = {"LoadBalancers": []}
        with pytest.raises(ProviderException):
            provider.describe_load_balancer(load_balancer_arn="arn:x")

    def test_full_response(self, provider):
        mc = MagicMock()
        provider._elbv2_client = mc
        lb_arn = "arn:alb"
        mc.describe_load_balancers.return_value = {
            "LoadBalancers": [{"LoadBalancerArn": lb_arn, "LoadBalancerName": "alb"}]
        }
        pag = MagicMock()
        pag.paginate.return_value = [{"Listeners": [{"Port": 443}]}]
        mc.get_paginator.return_value = pag
        mc.describe_target_groups.return_value = {
            "TargetGroups": [{"TargetGroupArn": "arn:tg", "TargetGroupName": "tg"}]
        }
        mc.describe_target_health.return_value = {
            "TargetHealthDescriptions": [{"TargetHealth": {"State": "healthy"}}]
        }
        result = provider.describe_load_balancer(load_balancer_arn=lb_arn)
        assert result["LoadBalancer"]["LoadBalancerName"] == "alb"
        assert result["Listeners"][0]["Port"] == 443
        assert result["TargetGroups"][0]["TargetHealthDescriptions"][0]["TargetHealth"]["State"] == "healthy"

    def test_health_error_does_not_raise(self, provider):
        mc = MagicMock()
        provider._elbv2_client = mc
        lb_arn = "arn:x"
        mc.describe_load_balancers.return_value = {
            "LoadBalancers": [{"LoadBalancerArn": lb_arn, "LoadBalancerName": "x"}]
        }
        pag = MagicMock()
        pag.paginate.return_value = [{"Listeners": []}]
        mc.get_paginator.return_value = pag
        mc.describe_target_groups.return_value = {
            "TargetGroups": [{"TargetGroupArn": "arn:tg", "TargetGroupName": "tg"}]
        }
        mc.describe_target_health.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "Op"
        )
        result = provider.describe_load_balancer(load_balancer_arn=lb_arn)
        assert result["TargetGroups"][0]["TargetHealthDescriptions"] == []

    def test_multiple_target_groups(self, provider):
        mc = MagicMock()
        provider._elbv2_client = mc
        lb_arn = "arn:alb"
        mc.describe_load_balancers.return_value = {"LoadBalancers": [{"LoadBalancerArn": lb_arn}]}
        pag = MagicMock()
        pag.paginate.return_value = [{"Listeners": []}]
        mc.get_paginator.return_value = pag
        tgs = [{"TargetGroupArn": f"arn:tg{i}", "TargetGroupName": f"tg{i}"} for i in range(3)]
        mc.describe_target_groups.return_value = {"TargetGroups": tgs}
        mc.describe_target_health.return_value = {"TargetHealthDescriptions": []}
        result = provider.describe_load_balancer(load_balancer_arn=lb_arn)
        assert len(result["TargetGroups"]) == 3


# ===========================================================================
# _query dispatch
# ===========================================================================


class TestQueryDispatch:
    def _empty_ecs(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        pag = MagicMock()
        pag.paginate.return_value = [{"clusterArns": []}]
        mc.get_paginator.return_value = pag
        return mc

    def test_unknown_raises(self, provider):
        with pytest.raises(NotImplementedError):
            provider._query("totally_unknown")

    def test_list_clusters(self, provider):
        self._empty_ecs(provider)
        assert provider._query("list_clusters") == []

    def test_stop_task(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        mc.stop_task.return_value = {"task": {"lastStatus": "STOPPED"}}
        result = provider._query("stop_task", cluster="c", task="t")
        assert result["lastStatus"] == "STOPPED"

    def test_update_service(self, provider):
        mc = MagicMock()
        provider._ecs_client = mc
        mc.update_service.return_value = {"service": {"serviceName": "s"}}
        result = provider._query("update_service", cluster="c", service="s")
        assert result["serviceName"] == "s"

    def test_list_load_balancers(self, provider):
        mc = MagicMock()
        provider._elbv2_client = mc
        pag = MagicMock()
        pag.paginate.return_value = [{"LoadBalancers": []}]
        mc.get_paginator.return_value = pag
        assert provider._query("list_load_balancers") == []


# ===========================================================================
# Provider metadata
# ===========================================================================


class TestMetadata:
    def test_display_name(self):
        assert AwsEcsProvider.PROVIDER_DISPLAY_NAME == "AWS ECS"

    def test_category(self):
        assert "Cloud Infrastructure" in AwsEcsProvider.PROVIDER_CATEGORY

    def test_mandatory_scopes(self):
        mandatory = {s.name for s in AwsEcsProvider.PROVIDER_SCOPES if s.mandatory}
        assert "ecs:ListClusters" in mandatory
        assert "ecs:DescribeClusters" in mandatory

    def test_all_methods_present(self):
        names = {m.func_name for m in AwsEcsProvider.PROVIDER_METHODS}
        for n in [
            "list_clusters", "list_services", "list_tasks",
            "list_load_balancers", "describe_load_balancer",
            "stop_task", "update_service",
        ]:
            assert n in names, f"Missing method: {n}"

    def test_scope_count(self):
        assert len(AwsEcsProvider.PROVIDER_SCOPES) >= 5

    def test_method_count(self):
        assert len(AwsEcsProvider.PROVIDER_METHODS) >= 5
