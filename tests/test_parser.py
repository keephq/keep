# here we are going to create all needed tests for the parser.py parse function
import builtins
import json
import os
import unittest.mock as mock
from pathlib import Path

import pytest
import requests
import yaml
from fastapi import HTTPException

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.contextmanager.contextmanager import ContextManager
from keep.parser.parser import Parser
from keep.providers.mock_provider.mock_provider import MockProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.step.step import Step
from keep.storagemanager.storagemanagerfactory import StorageManagerTypes
from keep.workflowmanager.workflowstore import WorkflowStore


def test_parse_with_nonexistent_file(db_session):
    workflow_store = WorkflowStore()
    # Expected error when a given input does not describe an existing file
    with pytest.raises(HTTPException) as e:
        workflow = workflow_store.get_workflow(SINGLE_TENANT_UUID, "test-not-found")
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


# This test depends on the previous one because of global providers configuration
@pytest.mark.xfail
def test_parse_with_alert_source_with_no_providers_file():
    parser = Parser()
    with pytest.raises(TypeError):
        parser.parse(str(workflow_path))


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
        parser = parse_env_setup(context_manager)

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
        parser = parse_env_setup(context_manager)

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
        parser = parse_file_setup(context_manager)

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
