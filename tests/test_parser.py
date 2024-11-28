# here we are going to create all needed tests for the parser.py parse function
import builtins
import json
import time
import uuid
from pathlib import Path

import pytest
import requests
import yaml
from fastapi import HTTPException

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.action import Action
from keep.contextmanager.contextmanager import ContextManager
from keep.parser.parser import Parser, ParserUtils
from keep.providers.mock_provider.mock_provider import MockProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.step.step import Step
from keep.workflowmanager.workflowstore import WorkflowStore


def test_parse_with_nonexistent_file(db_session):
    workflow_store = WorkflowStore()
    # Expected error when a given input does not describe an existing file
    with pytest.raises(HTTPException) as e:
        workflow_store.get_workflow(SINGLE_TENANT_UUID, "test-not-found")
    assert e.value.status_code == 404


def test_parse_with_nonexistent_url(monkeypatch):
    # Mocking requests.get to always raise a ConnectionError
    def mock_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError

    monkeypatch.setattr(requests, "get", mock_get)
    workflow_store = WorkflowStore()
    # Expected error when a given input does not describe an existing URL
    with pytest.raises(requests.exceptions.ConnectionError):
        workflow_store.get_workflows_from_path(
            SINGLE_TENANT_UUID, "https://ThisWebsiteDoNotExist.com"
        )


path_to_test_resources = Path(__file__).parent / "workflows"
workflow_path = str(path_to_test_resources / "db_disk_space_for_testing.yml")
providers_path = str(path_to_test_resources / "providers_for_testing.yaml")


def test_parse_sanity_check(db_session):
    workflow_store = WorkflowStore()
    parsed_workflows = workflow_store.get_workflows_from_path(
        SINGLE_TENANT_UUID, workflow_path, providers_path
    )
    assert parsed_workflows is not None
    assert (
        len(parsed_workflows) > 0
    ), "caution: the expected output is a list with at least one alert, instead got non "
    for index, parse_workflow in enumerate(parsed_workflows):
        print(
            "validating parsed alert #"
            + str(index + 1)
            + " out of "
            + str(len(parsed_workflows))
        )
        assert len(parse_workflow.workflow_actions) > 0
        assert parse_workflow.workflow_id is not None
        assert len(parse_workflow.workflow_owners) > 0 and all(
            parse_workflow.workflow_owners
        )
        assert len(parse_workflow.workflow_tags) > 0 and all(
            isinstance(item, str) for item in parse_workflow.workflow_tags
        )
        assert len(parse_workflow.workflow_steps) > 0 and all(
            type(item) == Step for item in parse_workflow.workflow_steps
        )


def test_parse_all_alerts(db_session):
    workflow_store = WorkflowStore()
    all_workflows = workflow_store.get_all_workflows_with_last_execution(
        tenant_id=SINGLE_TENANT_UUID
    )
    # Complete the asserts:
    assert len(all_workflows) == 2  # Assuming two mock alert files were returned
    # You can add more specific assertions based on the content of mock_files and how they are parsed into alerts.


def parse_env_setup(context_manager):
    parser = Parser()
    parser._parse_providers_from_env(context_manager=context_manager)
    return parser


class TestParseProvidersFromEnv:
    def test_parse_providers_from_env_empty(self, monkeypatch, context_manager):
        # ARRANGE
        monkeypatch.setenv("KEEP_PROVIDERS", "")

        # ACT
        parse_env_setup(context_manager=context_manager)

        # ASSERT
        assert context_manager.providers_context == {}

    def test_parse_providers_from_env_providers(self, monkeypatch, context_manager):
        # ARRANGE
        providers_dict = {
            "slack-demo": {"authentication": {"webhook_url": "https://not.a.real.url"}}
        }
        monkeypatch.setenv("KEEP_PROVIDERS", json.dumps(providers_dict))

        # ACT
        parse_env_setup(context_manager=context_manager)

        # ASSERT
        assert context_manager.providers_context == providers_dict

    def test_parse_providers_from_env_providers_bad_json(
        self, monkeypatch, context_manager
    ):
        # ARRANGE
        providers_str = '{"slack-demo": {"authentication": {"webhook_url": '
        monkeypatch.setenv("KEEP_PROVIDERS", providers_str)

        # ACT
        parse_env_setup(context_manager=context_manager)

        # ASSERT
        assert context_manager.providers_context == {}


class TestProviderFromEnv:
    def test_parse_provider_from_env_empty(self, monkeypatch, context_manager):
        # ARRANGE
        provider_name = "TEST_NAME_STUB"
        provider_dict = {"hi": 0}
        monkeypatch.setenv(f"KEEP_PROVIDER_{provider_name}", json.dumps(provider_dict))

        # ACT
        parse_env_setup(context_manager)

        # ASSERT
        expected = {provider_name.replace("_", "-").lower(): provider_dict}
        assert context_manager.providers_context == expected

    def test_parse_provider_from_env_provider_bad_json(
        self, monkeypatch, context_manager
    ):
        # ARRANGE
        provider_name = "BAD"
        providers_str = '{"authentication": {"webhook_url": '
        monkeypatch.setenv(f"KEEP_PROVIDER_{provider_name}", providers_str)

        # ACT
        parse_env_setup(context_manager)

        # ASSERT
        assert context_manager.providers_context == {}

    def test_parse_provider_from_env_provider_var_missing_name(
        self, monkeypatch, context_manager
    ):
        # ARRANGE
        provider_name = ""
        provider_dict = {"hi": 1}
        monkeypatch.setenv(f"KEEP_PROVIDER_{provider_name}", json.dumps(provider_dict))

        # ACT
        parse_env_setup(context_manager)

        # ASSERT
        expected = {provider_name.replace("_", "-").lower(): provider_dict}

        # This might be a bug?
        # It will create a provider context with an empty string as a provider name: {'': {'hi': 1}}
        assert context_manager.providers_context == expected

        # I would expect it to not create the provider
        # assert parser.context_manager.providers_context == {}


def parse_file_setup(context_manager):
    parser = Parser()
    parser._parse_providers_from_file(context_manager, "whatever")
    return parser


class TestProvidersFromFile:
    def test_parse_providers_from_file(self, monkeypatch, mocker, context_manager):
        # ARRANGE
        providers_dict = {
            "providers-file-provider": {
                "authentication": {"webhook_url": "https://not.a.real.url"}
            }
        }

        # Mocking yaml.safeload to return a good provider
        # This mocks the behavior of a successful file read, with a good yaml format (happy path)
        def mock_safeload(*args, **kwargs):
            return providers_dict

        monkeypatch.setattr(
            builtins, "open", mocker.mock_open(read_data="does not matter")
        )
        monkeypatch.setattr(yaml, "safe_load", mock_safeload)

        # ACT
        parse_file_setup(context_manager)

        # ASSERT
        assert context_manager.providers_context == providers_dict

    def test_parse_providers_from_file_bad_yaml(
        self, monkeypatch, mocker, context_manager
    ):
        # ARRANGE

        # Mocking yaml.safeload to simulate a malformed yaml file
        def mock_safeload(*args, **kwargs):
            raise yaml.YAMLError

        monkeypatch.setattr(
            builtins, "open", mocker.mock_open(read_data="does not matter")
        )
        monkeypatch.setattr(yaml, "safe_load", mock_safeload)

        # ACT/ASSERT
        with pytest.raises(yaml.YAMLError):
            parse_file_setup(context_manager)


class TestParseAlert:
    alert_id = "test-alert"
    alert = {"id": alert_id}

    def test_parse_alert_id(self):
        # ARRANGE
        parser = Parser()

        # ACT
        parsed_id = parser._parse_id(self.alert)

        # ASSERT
        assert parsed_id == self.alert_id

    def test_parse_alert_id_invalid(self):
        # ARRANGE
        parser = Parser()

        # ACT / ASSERT
        with pytest.raises(ValueError):
            parser._parse_id({"invalid": "not-an-id"})

        # ASSERT
        assert parser._parse_id({"id": ""}) == ""

    def test_parse_alert_steps(self):
        # ARRANGE
        provider_id = "mock"
        description = "test description"
        authentication = ""
        context_manager = ContextManager(tenant_id="mock", workflow_id=None)
        expected_provider = MockProvider(
            context_manager=context_manager,
            provider_id=provider_id,
            config=ProviderConfig(
                authentication=authentication, description=description
            ),
        )

        step = {
            "name": "mock-step",
            "provider": {
                "type": provider_id,
                "config": {
                    "description": description,
                    "authentication": "",
                },
            },
        }

        parser = Parser()

        # ACT / ASSERT
        provider = parser._get_step_provider(context_manager, step)

        # ASSERT
        assert provider.provider_id == expected_provider.provider_id
        assert provider.provider_type == expected_provider.provider_id


## Test Case for reusable actions
path_to_test_reusable_resources = Path(__file__).parent / "workflows"
reusable_workflow_path = str(path_to_test_resources / "reusable_alert_for_testing.yml")
reusable_workflow_with_action_path = str(
    path_to_test_resources / "reusable_alert_with_actions_for_testing.yml"
)
reusable_providers_path = str(path_to_test_resources / "providers_for_testing.yaml")
reusable_actions_path = str(path_to_test_resources / "reusable_actions_for_testing.yml")


class TestReusableActionWithWorkflow:

    def test_if_action_is_expanded(self, db_session):
        workflow_store = WorkflowStore()
        workflows = workflow_store.get_workflows_from_path(
            tenant_id=SINGLE_TENANT_UUID,
            workflow_path=reusable_workflow_path,
            providers_file=reusable_providers_path,
            actions_file=reusable_actions_path,
        )

        # parser should pass sanity check
        assert workflows is not None

        for workflow in workflows:
            actions = workflow.context_manager.actions_context
            assert len(actions) > 0
            for action_key, action_data in actions.items():
                assert "provider" in action_data

            assert (
                actions.get("@trigger-slack2", {}).get("provider", {}).get("type")
                == "slack"
            )

    def test_load_actions_config(self, db_session):
        parser = Parser()

        # load master workflow configuration
        workflow = {}
        with open(reusable_workflow_path, "r") as wfd:
            workflow_configuration = yaml.safe_load(wfd)

        # Case 1: check if only one action is loaded from reusable_actions_path
        context_manager = ContextManager(tenant_id="mock", workflow_id=None)
        workflow = workflow_configuration.get("workflow") or workflow_configuration.get(
            "alert"
        )
        parser._load_actions_config(
            SINGLE_TENANT_UUID,
            context_manager,
            workflow=workflow,
            actions_file=reusable_actions_path,
            workflow_actions=None,
        )
        assert len(context_manager.actions_context) == 1

        # Case 2: check if actions are also loaded from master_file
        workflow = {}
        with open(reusable_workflow_with_action_path, "r") as wfd:
            workflow_configuration = yaml.safe_load(wfd)
        context_manager = ContextManager(tenant_id="mock", workflow_id=None)
        workflow = workflow_configuration.get("workflow") or workflow_configuration.get(
            "alert"
        )
        workflow_actions = workflow_configuration.get("actions")
        parser._load_actions_config(
            SINGLE_TENANT_UUID,
            context_manager,
            workflow=workflow,
            actions_file=reusable_actions_path,
            workflow_actions=workflow_actions,
        )
        assert len(context_manager.actions_context) == 2

        # Case 3: check if actions are also loaded from database
        context_manager = ContextManager(tenant_id="mock", workflow_id=None)
        workflow_action = workflow_actions[0]
        action = Action(
            id=str(uuid.uuid4()),
            tenant_id=SINGLE_TENANT_UUID,
            use="@trigger-slack",
            name="trigger-slack",
            description="None",
            action_raw=yaml.dump(workflow_action),
            installed_by="pytest",
            installation_time=time.time(),
        )
        db_session.add(action)
        db_session.commit()
        parser._load_actions_config(
            SINGLE_TENANT_UUID,
            context_manager,
            workflow=workflow,
            actions_file=None,
            workflow_actions=None,
        )
        assert len(context_manager.actions_context) == 1


class TestParserUtils:

    def test_deep_merge_dict(self):
        """Dictionary: if the merge combines recursively and prioritize values of source"""
        source = {"1": {"s11": "s11", "s12": "s12"}, "2": {"s21": "s21"}}
        dest = {"1": {"s11": "d11", "d11": "d11", "d12": "d12"}, "3": {"d31": "d31"}}
        expected_results = {
            "1": {"s11": "s11", "s12": "s12", "d11": "d11", "d12": "d12"},
            "2": {"s21": "s21"},
            "3": {"d31": "d31"},
        }
        results = ParserUtils.deep_merge(source, dest)
        assert expected_results == results

    def test_deep_merge_list(self):
        """List: if the merge combines recursively and prioritize values of source"""
        source = {"data": [{"s1": "s1"}, {"s2": "s2"}]}
        dest = {"data": [{"d1": "d1"}, {"d2": "d2"}, {"d3": "d3"}]}
        expected_results = {
            "data": [{"s1": "s1", "d1": "d1"}, {"s2": "s2", "d2": "d2"}, {"d3": "d3"}]
        }

        results = ParserUtils.deep_merge(source, dest)
        assert expected_results == results


class TestWorkflowUUIDGeneration:
    def test_generate_different_uuid_if_id_not_provided(self):
        parser = Parser()
        workflow = {"name": "test_workflow"}
        tenant_id = "test_tenant"
        generated_id = parser._get_workflow_id(tenant_id, workflow)
        assert generated_id is not None
        assert isinstance(generated_id, str)
        assert len(generated_id) == 36  # UUID length

    def test_use_provided_id(self):
        parser = Parser()
        workflow = {"id": "test_id", "name": "test_workflow"}
        tenant_id = "test_tenant"
        generated_id = parser._get_workflow_id(tenant_id, workflow)
        assert generated_id == "test_id"


class TestWorkflowInvalidFlag:
    def test_workflow_invalid_flag(self):
        parser = Parser()
        workflow = {"name": "test_workflow", "invalid": True}
        tenant_id = "test_tenant"
        parsed_workflow = parser._parse_workflow(tenant_id, workflow, None)
        assert parsed_workflow.invalid is True

    def test_workflow_valid_flag(self):
        parser = Parser()
        workflow = {"name": "test_workflow", "invalid": False}
        tenant_id = "test_tenant"
        parsed_workflow = parser._parse_workflow(tenant_id, workflow, None)
        assert parsed_workflow.invalid is False
