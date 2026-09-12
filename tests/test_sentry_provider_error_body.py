"""Regression tests for SentryProvider._error_detail.

validate_scopes() is called by ProvidersService.provision_providers() at APPLICATION
STARTUP, and the exception is not caught there. So any error path that assumes a JSON
body turns a failed scope check into a backend crash loop rather than a reported scope.

Sentry does not guarantee a JSON body on errors: a 404 from an endpoint that no longer
exists returns an EMPTY body. `project:write` is validated by POSTing to the legacy
per-project endpoint /projects/{org}/{project}/plugins/webhooks/, which modern Sentry
answers with exactly that.
"""
import unittest
from unittest.mock import MagicMock

from keep.providers.sentry_provider.sentry_provider import SentryProvider


def _response(status_code, *, json_body=None, raises=False, url="https://sentry.io/x"):
    r = MagicMock()
    r.status_code = status_code
    r.url = url
    r.ok = 200 <= status_code < 300
    if raises:
        # requests raises ValueError (JSONDecodeError subclasses it) on an empty body
        r.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")
    else:
        r.json.return_value = json_body
    return r


class TestSentryErrorDetail(unittest.TestCase):
    def test_empty_body_does_not_raise(self):
        """The regression: a 404 with an empty body must not propagate."""
        detail = SentryProvider._error_detail(_response(404, raises=True))
        self.assertIsInstance(detail, str)
        self.assertIn("404", detail)

    def test_detail_is_used_when_present(self):
        detail = SentryProvider._error_detail(
            _response(403, json_body={"detail": "You do not have permission"})
        )
        self.assertEqual(detail, "You do not have permission")

    def test_falls_back_when_json_is_not_an_object(self):
        """Sentry returns a bare list from some endpoints."""
        detail = SentryProvider._error_detail(_response(400, json_body=["nope"]))
        self.assertIsInstance(detail, str)
        self.assertIn("400", detail)

    def test_falls_back_when_detail_is_absent_or_empty(self):
        for body in ({}, {"detail": ""}, {"error": "other shape"}):
            with self.subTest(body=body):
                detail = SentryProvider._error_detail(_response(500, json_body=body))
                self.assertIsInstance(detail, str)
                self.assertIn("500", detail)


if __name__ == "__main__":
    unittest.main()
