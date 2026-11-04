import pytest
from sqlmodel import select

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.preset import Preset
from tests.fixtures.client import client, test_app  # noqa: F401

COLUMN_OPTIONS = [
    {"label": "column_visibility", "value": {"severity": True, "source": False}},
    {"label": "column_order", "value": ["severity", "source"]},
    {
        "label": "column_rename_mapping",
        "value": {"severity": "Priority"},
    },
    {
        "label": "column_time_formats",
        "value": {"lastReceived": "relative"},
    },
    {"label": "column_list_formats", "value": {"labels": "comma-separated"}},
]


def _query_options(suffix):
    return [
        {"label": "CEL", "value": f'severity == "{suffix}"'},
        {
            "label": "SQL",
            "value": {"sql": "severity = :severity", "params": {"severity": suffix}},
        },
    ]


def _create_preset(db_session, options):
    preset = Preset(
        tenant_id=SINGLE_TENANT_UUID,
        created_by="test@keephq.dev",
        name="Custom preset",
        options=options,
    )
    db_session.add(preset)
    db_session.commit()
    db_session.refresh(preset)
    return preset


def _update_preset(client, preset, options):
    return client.put(
        f"/preset/{preset.id}",
        json={
            "name": preset.name,
            "options": options,
            "is_private": False,
            "is_noisy": False,
            "tags": [],
            "counter_shows_firing_only": True,
        },
    )


def _options_by_label(options):
    return {option["label"].lower(): option["value"] for option in options}


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_update_preset_preserves_column_configuration(db_session, client, test_app):
    preset = _create_preset(db_session, _query_options("warning") + COLUMN_OPTIONS)

    response = _update_preset(client, preset, _query_options("critical"))

    assert response.status_code == 200
    returned_options = _options_by_label(response.json()["options"])
    stored_preset = db_session.exec(
        select(Preset).where(Preset.id == preset.id)
    ).first()
    db_session.refresh(stored_preset)
    stored_options = _options_by_label(stored_preset.options)

    assert returned_options == stored_options
    assert returned_options == _options_by_label(
        _query_options("critical") + COLUMN_OPTIONS
    )


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_update_preset_without_column_configuration_updates_query_only(
    db_session, client, test_app
):
    preset = _create_preset(db_session, _query_options("warning"))

    response = _update_preset(client, preset, _query_options("critical"))

    assert response.status_code == 200
    assert response.json()["options"] == _query_options("critical")

    db_session.refresh(preset)
    assert preset.options == _query_options("critical")


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_repeated_preset_updates_replace_queries_without_duplicate_options(
    db_session, client, test_app
):
    preset = _create_preset(db_session, _query_options("info") + COLUMN_OPTIONS)
    submitted_column_option = {
        "label": "column_visibility",
        "value": {"severity": False},
    }

    first_response = _update_preset(
        client, preset, _query_options("warning") + [submitted_column_option]
    )
    second_response = _update_preset(client, preset, _query_options("critical"))

    assert first_response.status_code == 200
    first_options = first_response.json()["options"]
    assert _options_by_label(first_options) == _options_by_label(
        _query_options("warning") + COLUMN_OPTIONS
    )
    assert len(first_options) == len(_query_options("warning") + COLUMN_OPTIONS)

    assert second_response.status_code == 200
    returned_options = second_response.json()["options"]
    assert _options_by_label(returned_options) == _options_by_label(
        _query_options("critical") + COLUMN_OPTIONS
    )
    assert len(returned_options) == len(_query_options("critical") + COLUMN_OPTIONS)

    db_session.refresh(preset)
    assert preset.options == returned_options
