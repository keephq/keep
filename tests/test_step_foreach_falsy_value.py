"""
Test for Step._get_foreach_items crashing on a single falsy resolved value.

This reproduces the issue described in https://github.com/keephq/keep/issues/6721
where `_get_foreach_items` used the `X and Y or Z` idiom to decide whether to
return the single resolved foreach value directly or zip() multiple
`&&`-combined ones together:

    return len(foreach_items) == 1 and foreach_items[0] or zip(*foreach_items)

That idiom is only safe when `foreach_items[0]` is never falsy. If a
`foreach: "{{ ... }}"` reference legitimately resolves to a falsy scalar like
`0` or `False`, the expression falls through to `zip(*foreach_items)` even
though there is only one item, and `zip()` requires an iterable argument -
crashing with a TypeError instead of returning the resolved value.
"""

import uuid
from unittest.mock import MagicMock

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.contextmanager.contextmanager import ContextManager
from keep.step.step import Step, StepType


@pytest.mark.parametrize("falsy_value", [0, False, "", 0.0])
def test_get_foreach_items_returns_single_falsy_value_instead_of_crashing(falsy_value):
    context_manager = ContextManager(
        tenant_id=SINGLE_TENANT_UUID,
        workflow_id=str(uuid.uuid4()),
    )
    context_manager.set_step_context("check-count", results=falsy_value)

    step = Step(
        context_manager=context_manager,
        step_id="notify",
        config={"foreach": "{{ steps.check-count.results }}"},
        step_type=StepType.ACTION,
        provider=MagicMock(),
        provider_parameters={},
    )

    assert step._get_foreach_items() == falsy_value


def test_get_foreach_items_still_zips_multiple_references():
    context_manager = ContextManager(
        tenant_id=SINGLE_TENANT_UUID,
        workflow_id=str(uuid.uuid4()),
    )
    context_manager.set_step_context("a", results=[1, 2])
    context_manager.set_step_context("b", results=[3, 4])

    step = Step(
        context_manager=context_manager,
        step_id="notify",
        config={"foreach": "{{ steps.a.results }} && {{ steps.b.results }}"},
        step_type=StepType.ACTION,
        provider=MagicMock(),
        provider_parameters={},
    )

    assert list(step._get_foreach_items()) == [(1, 3), (2, 4)]


def test_get_foreach_items_returns_single_truthy_value_unchanged():
    context_manager = ContextManager(
        tenant_id=SINGLE_TENANT_UUID,
        workflow_id=str(uuid.uuid4()),
    )
    context_manager.set_step_context("items", results=[1, 2, 3])

    step = Step(
        context_manager=context_manager,
        step_id="notify",
        config={"foreach": "{{ steps.items.results }}"},
        step_type=StepType.ACTION,
        provider=MagicMock(),
        provider_parameters={},
    )

    assert step._get_foreach_items() == [1, 2, 3]
