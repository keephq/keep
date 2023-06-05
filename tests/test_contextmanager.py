"""
Test the context manager
"""
import json
import random
import tempfile

import pytest
from starlette_context import context, request_cycle_context

from keep.contextmanager.contextmanager import ContextManager, get_context_manager_id

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
def ctx_store() -> dict:
    """
    Create a context store
    """
    return {"X-Request-ID": random.randint(10000, 90000)}


@pytest.fixture
def mocked_context(ctx_store) -> None:
    with request_cycle_context(ctx_store):
        yield context


@pytest.fixture
def context_manager(mocked_context) -> ContextManager:
    """
    Create a context manager
    """
    with tempfile.NamedTemporaryFile() as fp:
        ContextManager.STATE_FILE = fp.name
        yield ContextManager()


@pytest.fixture
def context_manager_with_state(mocked_context) -> ContextManager:
    with tempfile.NamedTemporaryFile() as fp:
        ContextManager.STATE_FILE = fp.name
        fp.write(json.dumps(STATE_FILE_MOCK_DATA).encode())
        fp.seek(0)
        yield ContextManager()


def test_get_context_manager_id_no_starlette_context():
    """
    Test the get_context_manager_id function when starlette context is not available
    """
    assert get_context_manager_id() == "main"


def test_get_contexst_manager_id_with_starlette_context(mocked_context):
    """
    Test the get_context_manager_id function when starlette context is available with mock data§
    """
    assert isinstance(get_context_manager_id(), int)


def test_context_manager_set_alert_context(context_manager: ContextManager):
    """
    Test the set_alert_context function
    """
    context_manager.set_alert_context({"test": "mock"})
    assert context_manager.alert_context == {"test": "mock"}


def test_context_manager_get_alert_id(context_manager: ContextManager):
    """
    Test the get_alert_id function
    """
    context_manager.set_alert_context({"alert_id": "1234"})
    assert context_manager.get_alert_id() == "1234"


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


def test_context_manager_delete_instance(context_manager: ContextManager):
    context_manager_id = get_context_manager_id()
    context_manager.delete_instance()
    instances = context_manager.__getattribute__("_ContextManager__instances")
    assert context_manager_id not in instances


def test_context_manager_set_last_alert_run(context_manager: ContextManager):
    """
    Test the set_last_alert_run function
    """
    alert_id = "mock_alert"
    alert_context = {"mock": "mock"}
    alert_status = "firing"
    context_manager.set_last_alert_run(alert_id, alert_context, alert_status)
    assert alert_id in context_manager.state
    with open(context_manager.STATE_FILE, "r") as f:
        state = json.load(f)
    assert alert_id in state


def test_context_manager_get_last_alert_run(context_manager: ContextManager):
    alert_id = "mock_alert"
    alert_context = {"mock": "mock"}
    alert_status = "firing"
    last_run = context_manager.get_last_alert_run(alert_id)
    assert last_run == {}
    context_manager.set_last_alert_run(alert_id, alert_context, alert_status)
    last_run = context_manager.get_last_alert_run(alert_id)
    assert last_run["alert_status"] == alert_status


def test_context_manager_singleton(context_manager: ContextManager):
    with pytest.raises(Exception):
        ContextManager()
