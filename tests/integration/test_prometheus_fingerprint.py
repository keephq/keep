import os
import logging

logging.disable(logging.CRITICAL)

# ─── Disable background services BEFORE importing app ───
os.environ["SCHEDULER"] = "false"
os.environ["CONSUMER"] = "false"
os.environ["KEEP_TOPOLOGY_PROCESSOR"] = "false"
os.environ["KEEP_USE_LIMITER"] = "false"
os.environ["KEEP_METRICS"] = "false"
os.environ["KEEP_OTEL_ENABLED"] = "false"
os.environ["KEEP_DISABLE_SECRETS"] = "true"

import pytest
from fastapi.testclient import TestClient
from fastapi import Request
from fastapi.responses import JSONResponse

from keep.api.api import get_app

app = get_app()

# inject the minimal state so the real exception handler won’t blow up
@app.middleware("http")
async def _inject_test_state(request: Request, call_next):
    request.state.trace_id = "test-trace"
    request.state.tenant_id = "anonymous"
    return await call_next(request)

# catch‐all override just in case
@app.exception_handler(Exception)
async def _test_catch_all(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})


@pytest.mark.parametrize("body", [
    # 1) explicit fingerprint at root
    {
      "summary": "Test Prometheus Root Fingerprint",
      "labels": {
        "severity": "critical",
        "service": "test-service",
        "alertname": "TestPrometheusRoot"
      },
      "status": "firing",
      "annotations": { "summary": "Testing fingerprint at root level" },
      "fingerprint": "explicit-root-fingerprint-123"
    },
    # 2) explicit fingerprint in labels
    {
      "summary": "Test Prometheus Label Fingerprint",
      "labels": {
        "severity": "critical",
        "service": "test-service",
        "alertname": "TestPrometheusLabel",
        "fingerprint": "explicit-label-fingerprint-456"
      },
      "status": "firing",
      "annotations": { "summary": "Testing fingerprint in labels" }
    },
    # 3) no fingerprint → SHA is generated internally
    {
      "summary": "Test Prometheus No Fingerprint",
      "labels": {
        "severity": "critical",
        "service": "test-service",
        "alertname": "TestPrometheusNoFingerprint"
      },
      "status": "firing",
      "annotations": { "summary": "Testing with no fingerprint" }
    },
])
def test_prometheus_event_accepted(body):
    with TestClient(app) as client:
        response = client.post(
            "/alerts/event/prometheus",
            json=body,
            headers={"X-API-KEY": "localhost"},
        )

    # the API enqueues and returns 202
    assert response.status_code == 202

    # and returns a JSON body with a non‐empty "task_name"
    data = response.json()
    assert "task_name" in data
    assert isinstance(data["task_name"], str) and data["task_name"].strip() != ""
