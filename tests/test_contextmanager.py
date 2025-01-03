"""
Test the context manager
"""

import json
import tempfile

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.workflow import WorkflowExecution
from keep.contextmanager.contextmanager import ContextManager

STATE_FILE_MOCK_DATA = {
    "new-github-stars": [
        {
            "alert_status": "firing",
            "alert_context": {
                "alert_id": "new-github-stars",
                "alert_owners": [],
                "alert_tags": [],
                "alert_steps_context": {
                    "get-github-stars": {
                        "conditions": {
                            "assert": [
                                {
                                    "value": None,
                                    "compare_value": "1 == 0",
                                    "compare_to": None,
                                    "result": True,
                                    "type": "assert",
                                    "alias": None,
                                }
                            ]
                        },
                        "results": {
                            "stars": 928,
                            "new_stargazers": [
                                {
                                    "username": "talboren",
                                    "starred_at": "2023-04-05 20:51:38",
                                }
                            ],
                            "new_stargazers_count": 1,
                        },
                    },
                    "this": {
                        "conditions": {
                            "assert": [
                                {
                                    "value": None,
                                    "compare_value": "1 == 0",
                                    "compare_to": None,
                                    "result": True,
                                    "type": "assert",
                                    "alias": None,
                                }
                            ]
                        },
                        "results": {
                            "stars": 928,
                            "new_stargazers": [
                                {
                                    "username": "talboren",
                                    "starred_at": "2023-04-05 20:51:38",
                                }
                            ],
                            "new_stargazers_count": 1,
                        },
                    },
                },
            },
        }
    ]
}


@pytest.fixture
def context_manager_with_state(mocked_context) -> ContextManager:
    with tempfile.NamedTemporaryFile() as fp:
        import os

        print(fp.name)
        fp_name_split = fp.name.split("/")
        storage_manager_directory = "/".join(
            fp_name_split[0:-2] if len(fp_name_split) > 3 else fp_name_split[0:-1]
        )
        tenant_id = fp_name_split[-2] if len(fp_name_split) > 3 else ""
        file_name = fp_name_split[-1]
        print(
            f"storage_manager_directory: {storage_manager_directory} tenant_id: {tenant_id} file_name: {file_name}"
        )
        os.environ["KEEP_STATE_FILE"] = file_name
        os.environ["STORAGE_MANAGER_DIRECTORY"] = storage_manager_directory
        fp.write(json.dumps(STATE_FILE_MOCK_DATA).encode())
        fp.seek(0)
        context_manager = ContextManager(tenant_id=tenant_id, workflow_id="mock")
        yield context_manager


def test_context_manager_get_alert_id(context_manager: ContextManager):
    """
    Test the get_alert_id function
    """
    assert context_manager.get_workflow_id() == "1234"


def test_context_manager_get_full_context(context_manager_with_state: ContextManager):
    """
    Test the get_full_context function
    """
    full_context = context_manager_with_state.get_full_context()
    assert "steps" in full_context


def test_context_manager_set_for_each_context(context_manager: ContextManager):
    """
    Test the set_for_each_context function
    """
    context_manager.set_for_each_context("mock")
    assert context_manager.foreach_context == {"value": "mock"}


def test_context_manager_set_condition_results(context_manager: ContextManager):
    """
    Test the set_condition_results function
    """
    action_id = "mock_action"
    condition_name = "mock_condition"
    condition_type = "mock_type"
    compare_to = "mock_compare_to"
    compare_value = "mock_compare_value"
    result = "mock_result"
    condition_alias = "mock_alias"
    value = "mock_value"
    context_manager.set_condition_results(
        action_id=action_id,
        condition_name=condition_name,
        condition_type=condition_type,
        compare_to=compare_to,
        compare_value=compare_value,
        result=result,
        condition_alias=condition_alias,
        value=value,
    )
    assert (
        context_manager.steps_context[action_id]["conditions"][condition_name][0][
            "type"
        ]
        == condition_type
    )
    assert context_manager.foreach_context["compare_to"] == compare_to
    assert context_manager.foreach_context["compare_value"] == compare_value
    assert context_manager.aliases[condition_alias] == result


def test_context_manager_set_step_provider_parameters(context_manager: ContextManager):
    """
    Test the set_step_provider_paremeters function
    """
    provider_params = {"mock": "mock"}
    context_manager.set_step_provider_paremeters("mock_step", provider_params)
    assert (
        context_manager.steps_context["mock_step"]["provider_parameters"]
        == provider_params
    )


def test_context_manager_set_step_context(context_manager: ContextManager):
    """
    Test the set_step_context function
    """
    step_id = "mock_step"
    results = "mock_results"
    foreach = True
    context_manager.set_step_context(step_id=step_id, results=results, foreach=foreach)
    assert context_manager.steps_context[step_id]["results"] == [results]
    assert context_manager.steps_context["this"]["results"] == [results]
    context_manager.set_step_context(step_id=step_id, results=results, foreach=False)
    assert context_manager.steps_context["this"]["results"] == results
    assert context_manager.steps_context[step_id]["results"] == results

@pytest.mark.asyncio
async def test_context_manager_get_last_alert_run(
    context_manager_with_state: ContextManager, db_session
):
    workflow_id = "test-id-1"
    alert_context = {"mock": "mock"}
    alert_status = "firing"
    context_manager_with_state.tenant_id = SINGLE_TENANT_UUID
    last_run = await context_manager_with_state.get_last_workflow_run(workflow_id)
    if last_run is None:
        pytest.fail("No workflow run found with the given workflow_id")
    assert last_run == WorkflowExecution(
        id="test-execution-id-1",
        workflow_id=workflow_id,
        tenant_id=SINGLE_TENANT_UUID,
        started=last_run.started,
        triggered_by="keep-test",
        status="success",
        execution_number=1,
        results={},
    )
    context_manager_with_state.set_last_workflow_run(
        workflow_id, alert_context, alert_status
    )


def test_context_manager_singleton(context_manager: ContextManager):
    with pytest.raises(Exception):
        ContextManager()
