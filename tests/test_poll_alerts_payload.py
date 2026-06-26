from keep.api.consts import FINGERPRINT_PAYLOAD_LIMIT, fingerprints_for_poll_payload, poll_alerts_payload


def test_fingerprints_for_poll_payload_within_limit():
    fingerprints = [f"fp-{index}" for index in range(FINGERPRINT_PAYLOAD_LIMIT)]
    assert fingerprints_for_poll_payload(fingerprints) == fingerprints


def test_fingerprints_for_poll_payload_above_limit_returns_empty():
    fingerprints = [f"fp-{index}" for index in range(FINGERPRINT_PAYLOAD_LIMIT + 1)]
    assert fingerprints_for_poll_payload(fingerprints) == []


class TestPollAlertsPayloadFingerprintsOnly:
    def test_returns_fingerprints_when_no_transitions(self):
        result = poll_alerts_payload(["fp-1", "fp-2"])
        assert result == {"fingerprints": ["fp-1", "fp-2"]}

    def test_empty_fingerprints(self):
        result = poll_alerts_payload([])
        assert result == {"fingerprints": []}

    def test_no_transition_fields_when_none(self):
        result = poll_alerts_payload(["fp-1"])
        assert "alerts" not in result
        assert "statuses" not in result
        assert "resolved_fingerprints" not in result


class TestPollAlertsPayloadWithTransitions:
    def test_includes_all_fields(self):
        transitions = [
            {"fingerprint": "fp-1", "status": "resolved", "previous_status": "acknowledged"},
            {"fingerprint": "fp-2", "status": "firing", "previous_status": None},
        ]
        result = poll_alerts_payload(["fp-1", "fp-2"], alert_transitions=transitions)

        assert result["fingerprints"] == ["fp-1", "fp-2"]
        assert result["alerts"] == transitions
        assert result["statuses"] == {"fp-1": "resolved", "fp-2": "firing"}
        assert result["resolved_fingerprints"] == ["fp-1"]

    def test_previous_status_null(self):
        transitions = [
            {"fingerprint": "fp-1", "status": "firing", "previous_status": None},
        ]
        result = poll_alerts_payload(["fp-1"], alert_transitions=transitions)
        assert result["alerts"][0]["previous_status"] is None

    def test_previous_status_present(self):
        transitions = [
            {"fingerprint": "fp-1", "status": "resolved", "previous_status": "firing"},
        ]
        result = poll_alerts_payload(["fp-1"], alert_transitions=transitions)
        assert result["alerts"][0]["previous_status"] == "firing"

    def test_statuses_map(self):
        transitions = [
            {"fingerprint": "fp-1", "status": "resolved", "previous_status": "firing"},
            {"fingerprint": "fp-2", "status": "acknowledged", "previous_status": "firing"},
            {"fingerprint": "fp-3", "status": "firing", "previous_status": None},
        ]
        result = poll_alerts_payload(
            ["fp-1", "fp-2", "fp-3"], alert_transitions=transitions
        )
        assert result["statuses"] == {
            "fp-1": "resolved",
            "fp-2": "acknowledged",
            "fp-3": "firing",
        }

    def test_resolved_fingerprints_derived(self):
        transitions = [
            {"fingerprint": "fp-1", "status": "resolved", "previous_status": "firing"},
            {"fingerprint": "fp-2", "status": "firing", "previous_status": None},
            {"fingerprint": "fp-3", "status": "resolved", "previous_status": "acknowledged"},
        ]
        result = poll_alerts_payload(
            ["fp-1", "fp-2", "fp-3"], alert_transitions=transitions
        )
        assert set(result["resolved_fingerprints"]) == {"fp-1", "fp-3"}

    def test_no_resolved_fingerprints_when_none_resolved(self):
        transitions = [
            {"fingerprint": "fp-1", "status": "firing", "previous_status": None},
        ]
        result = poll_alerts_payload(["fp-1"], alert_transitions=transitions)
        assert result["resolved_fingerprints"] == []


class TestPollAlertsPayloadOverLimit:
    def test_over_limit_returns_empty_fingerprints(self):
        fingerprints = [f"fp-{i}" for i in range(FINGERPRINT_PAYLOAD_LIMIT + 1)]
        transitions = [
            {"fingerprint": fp, "status": "firing", "previous_status": None}
            for fp in fingerprints
        ]
        result = poll_alerts_payload(fingerprints, alert_transitions=transitions)
        assert result == {"fingerprints": []}

    def test_over_limit_omits_transition_fields(self):
        fingerprints = [f"fp-{i}" for i in range(FINGERPRINT_PAYLOAD_LIMIT + 1)]
        result = poll_alerts_payload(fingerprints)
        assert "alerts" not in result
        assert "statuses" not in result
        assert "resolved_fingerprints" not in result

    def test_at_limit_includes_all_fields(self):
        fingerprints = [f"fp-{i}" for i in range(FINGERPRINT_PAYLOAD_LIMIT)]
        transitions = [
            {"fingerprint": fp, "status": "firing", "previous_status": None}
            for fp in fingerprints
        ]
        result = poll_alerts_payload(fingerprints, alert_transitions=transitions)
        assert result["fingerprints"] == fingerprints
        assert len(result["alerts"]) == FINGERPRINT_PAYLOAD_LIMIT
