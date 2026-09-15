"""Regression tests for AppdynamicsProvider._error_detail.

`get_user_id_by_name()` logs `extra=response.json()` when the AppDynamics controller
answers with a non-ok status. AppDynamics does not guarantee a JSON object body on
every error - a reverse proxy or WAF in front of the controller can return an HTML
page or plain text for a 401/403 instead. `response.json()` raises `ValueError` on a
non-JSON body, and stdlib logging's `extra=` requires a mapping, so even a JSON body
that isn't a dict (e.g. a bare list) breaks the same way. Either case turned an
auth/permission failure into an unrelated crash of the logging call itself.
"""

from unittest.mock import MagicMock

from keep.providers.appdynamics_provider.appdynamics_provider import (
    AppdynamicsProvider,
)


def _response(status_code, *, json_body=None, raises=False, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    r.ok = 200 <= status_code < 300
    if raises:
        # requests raises ValueError (JSONDecodeError subclasses it) on a non-JSON body
        r.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")
    else:
        r.json.return_value = json_body
    return r


class TestAppdynamicsErrorDetail:
    def test_non_json_body_does_not_raise(self):
        """The regression: an HTML/plain-text error body must not propagate."""
        detail = AppdynamicsProvider._error_detail(
            _response(401, raises=True, text="<html>Unauthorized</html>")
        )
        assert detail == {"status_code": 401, "text": "<html>Unauthorized</html>"}

    def test_json_object_body_is_returned_as_is(self):
        detail = AppdynamicsProvider._error_detail(
            _response(403, json_body={"message": "Insufficient permissions"})
        )
        assert detail == {"message": "Insufficient permissions"}

    def test_non_dict_json_body_falls_back(self):
        """AppDynamics-style non-object JSON (e.g. a bare list) must not crash logging."""
        detail = AppdynamicsProvider._error_detail(
            _response(400, json_body=["nope"], text='["nope"]')
        )
        assert detail == {"status_code": 400, "text": '["nope"]'}
