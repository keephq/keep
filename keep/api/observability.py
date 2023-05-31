import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.cloud_trace_propagator import CloudTraceFormatPropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider


def setup(app: FastAPI):
    # Configure the OpenTelemetry SDK
    service_name = os.environ.get("SERVICE_NAME", "keep-api")
    resource = Resource.create({"service.name": service_name})
    trace.set_tracer_provider(TracerProvider(resource=resource))

    # Enable trace context propagation
    propagator = CloudTraceFormatPropagator()
    set_global_textmap(propagator)

    # Auto-instrument FastAPI application
    FastAPIInstrumentor.instrument_app(app)

    # Enable OpenTelemetry Logging Instrumentation
    LoggingInstrumentor().instrument()
