"""
Test the context manager
"""
import json
import tempfile

import pytest
from starlette_context import context

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
        old_keep_state_file = os.environ["KEEP_STATE_FILE"]
        old_storage_manager_directory = os.environ["STORAGE_MANAGER_DIRECTORY"]
        fp_name_split = fp.name.split("/")
        storage_manager_directory = "/".join(fp_name_split[0:-2])
        tenant_id = fp_name_split[-2]
        file_name = fp_name_split[-1]
        os.environ["KEEP_STATE_FILE"] = file_name
        os.environ["STORAGE_MANAGER_DIRECTORY"] = storage_manager_directory
        fp.write(json.dumps(STATE_FILE_MOCK_DATA).encode())
        fp.seek(0)
        context_manager = ContextManager(tenant_id=tenant_id, workflow_id="mock")
        yield context_manager
        os.environ["KEEP_STATE_FILE"] = old_keep_state_file
        os.environ["STORAGE_MANAGER_DIRECTORY"] = old_storage_manager_directory


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
    assert (
        full_context["state"]["new-github-stars"][0]["alert_context"]["alert_id"]
        == STATE_FILE_MOCK_DATA["new-github-stars"][0]["alert_context"]["alert_id"]
    )
    assert "state" in full_context
    full_context = context_manager_with_state.get_full_context(exclude_state=True)
    assert "state" not in full_context


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
        context_manager.actions_context[action_id]["conditions"][condition_name][0][
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


# def test_context_manager_delete_instance(context_manager: ContextManager):
#     context_manager_id = get_context_manager_id()
#     context_manager.delete_instance()
#     instances = context_manager.__getattribute__("_ContextManager__instances")
#     assert context_manager_id not in instances


def test_context_manager_set_last_alert_run(context_manager_with_state: ContextManager):
    """
    Test the set_last_alert_run function
    """
    alert_id = "mock_alert"
    alert_context = {"mock": "mock"}
    alert_status = "firing"
    context_manager_with_state.set_last_workflow_run(
        alert_id, alert_context, alert_status
    )
    context_manager_with_state.dump()
    assert alert_id in context_manager_with_state.state
    state = context_manager_with_state.storage_manager.get_file(
        context_manager_with_state.tenant_id, context_manager_with_state.state_file
    )
    state = json.loads(state)
    assert alert_id in state


def test_context_manager_get_last_alert_run(context_manager_with_state: ContextManager):
    alert_id = "mock_alert"
    alert_context = {"mock": "mock"}
    alert_status = "firing"
    last_run = context_manager_with_state.get_last_workflow_run(alert_id)
    assert last_run == {}
    context_manager_with_state.set_last_workflow_run(
        alert_id, alert_context, alert_status
    )
    last_run = context_manager_with_state.get_last_workflow_run(alert_id)
    assert last_run["workflow_status"] == alert_status


def test_context_manager_singleton(context_manager: ContextManager):
    with pytest.raises(Exception):
        ContextManager()
