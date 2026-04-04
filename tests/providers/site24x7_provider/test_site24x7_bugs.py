"""
Tests for Site24x7 provider bug fixes.

Bug 1 (issue #6195): STATUS "UP" was never mapped to AlertStatus.RESOLVED —
    _format_alert() passed no `status` argument to AlertDto, so it always
    defaulted to AlertStatus.FIRING via the root_validator fallback.

Bug 2 (issue #6196): TAGS field from the webhook payload was never read —
    _format_alert() ignored TAGS entirely, so AlertDto.labels was always {}.
"""

import pytest

from keep.providers.site24x7_provider.site24x7_provider import Site24X7Provider


def _minimal_event(**kwargs) -> dict:
    """Return a minimal valid Site24x7 webhook payload, with optional overrides."""
    base = {
        "MONITORURL": "https://example.com",
        "INCIDENT_TIME_ISO": "2026-04-04T10:00:00Z",
        "INCIDENT_REASON": "Connection refused",
        "MONITORNAME": "Website - example.com",
        "MONITOR_ID": "12345",
        "STATUS": "DOWN",
        "TAGS": "",
    }
    base.update(kwargs)
    return base


class TestStatusMapping:
    """Bug #6195: STATUS field must drive AlertDto.status, not just severity."""

    def test_status_up_resolves_alert(self):
        """STATUS 'UP' (monitor recovered) must produce AlertStatus.RESOLVED."""
        alert = Site24X7Provider._format_alert(_minimal_event(STATUS="UP"))
        assert alert.status == "resolved"

    def test_status_down_fires_alert(self):
        """STATUS 'DOWN' must produce AlertStatus.FIRING."""
        alert = Site24X7Provider._format_alert(_minimal_event(STATUS="DOWN"))
        assert alert.status == "firing"

    def test_status_trouble_fires_alert(self):
        """STATUS 'TROUBLE' must produce AlertStatus.FIRING."""
        alert = Site24X7Provider._format_alert(_minimal_event(STATUS="TROUBLE"))
        assert alert.status == "firing"

    def test_status_critical_fires_alert(self):
        """STATUS 'CRITICAL' must produce AlertStatus.FIRING."""
        alert = Site24X7Provider._format_alert(_minimal_event(STATUS="CRITICAL"))
        assert alert.status == "firing"

    def test_status_unknown_defaults_to_firing(self):
        """Unknown STATUS values must fall back to AlertStatus.FIRING."""
        alert = Site24X7Provider._format_alert(_minimal_event(STATUS="SOMETHING_NEW"))
        assert alert.status == "firing"

    def test_status_up_preserves_info_severity(self):
        """STATUS 'UP' must still map severity to INFO (existing SEVERITIES_MAP)."""
        alert = Site24X7Provider._format_alert(_minimal_event(STATUS="UP"))
        assert alert.severity == "info"


class TestTagsParsing:
    """Bug #6196: TAGS field must be parsed and stored in AlertDto.labels."""

    def test_tags_key_value_pairs(self):
        """'env:prod,team:backend' must produce {'env': 'prod', 'team': 'backend'}."""
        alert = Site24X7Provider._format_alert(
            _minimal_event(TAGS="env:prod,team:backend")
        )
        assert alert.labels == {"env": "prod", "team": "backend"}

    def test_tags_empty_string(self):
        """Empty TAGS string must produce an empty labels dict."""
        alert = Site24X7Provider._format_alert(_minimal_event(TAGS=""))
        assert alert.labels == {}

    def test_tags_field_absent(self):
        """Missing TAGS key in payload must produce an empty labels dict."""
        event = _minimal_event()
        event.pop("TAGS")
        alert = Site24X7Provider._format_alert(event)
        assert alert.labels == {}

    def test_tags_plain_name_without_value(self):
        """Tag without ':' separator must map to {'tagname': 'tagname'}."""
        alert = Site24X7Provider._format_alert(_minimal_event(TAGS="tagname"))
        assert alert.labels == {"tagname": "tagname"}

    def test_tags_mixed_plain_and_kv(self):
        """Mix of plain tags and key:value tags must all be captured."""
        alert = Site24X7Provider._format_alert(
            _minimal_event(TAGS="env:prod,critical")
        )
        assert alert.labels == {"env": "prod", "critical": "critical"}

    def test_tags_value_containing_colon(self):
        """Tag value may itself contain ':' — only split on the first one."""
        alert = Site24X7Provider._format_alert(
            _minimal_event(TAGS="url:https://example.com")
        )
        assert alert.labels == {"url": "https://example.com"}

    def test_tags_whitespace_trimmed(self):
        """Spaces around tag names and values must be stripped."""
        alert = Site24X7Provider._format_alert(
            _minimal_event(TAGS=" env : prod , team : backend ")
        )
        assert alert.labels == {"env": "prod", "team": "backend"}

    def test_tags_as_dict_passed_through(self):
        """If TAGS is already a dict, it must be used as-is."""
        alert = Site24X7Provider._format_alert(
            _minimal_event(TAGS={"env": "prod", "team": "backend"})
        )
        assert alert.labels == {"env": "prod", "team": "backend"}


class TestFormatAlertFields:
    """Verify that the other AlertDto fields are still mapped correctly."""

    def test_source_is_site24x7(self):
        """source must always be ['site24x7']."""
        alert = Site24X7Provider._format_alert(_minimal_event())
        assert alert.source == ["site24x7"]

    def test_basic_fields_mapped(self):
        """Core fields from the webhook payload must be present."""
        alert = Site24X7Provider._format_alert(_minimal_event())
        assert "example.com" in str(alert.url)
        assert alert.name == "Website - example.com"
        assert alert.id == "12345"
        assert alert.description == "Connection refused"
        assert alert.lastReceived.startswith("2026-04-04T10:00:00")
