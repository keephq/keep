import os

from fastapi import FastAPI, Request
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.cloud_trace_propagator import CloudTraceFormatPropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import get_current_span


def setup(app: FastAPI):
    # Configure the OpenTelemetry SDK
    service_name = os.environ.get("SERVICE_NAME", "keep-api")
    resource = Resource.create({"service.name": service_name})
    trace.set_tracer_provider(TracerProvider(resource=resource))

    # Enable trace context propagation
    propagator = CloudTraceFormatPropagator()
    set_global_textmap(propagator)

    # let's create a simple middleware that will add a trace id to each request
    # this will allow us to trace requests through the system and in the exception handler
    class TraceIDMiddleware:
        async def __call__(self, request: Request, call_next):
            tracer = trace.get_current_span()
            trace_id = tracer.get_span_context().trace_id
            request.state.trace_id = format(trace_id, "032x")
            response = await call_next(request)
            return response

    app.middleware("http")(TraceIDMiddleware())
    # Auto-instrument FastAPI application
    FastAPIInstrumentor.instrument_app(app)

    # Enable OpenTelemetry Logging Instrumentation
    LoggingInstrumentor().instrument()


def get_trace_id():
    current_span = get_current_span()
    if current_span.is_recording():
        trace_id = current_span.get_span_context().trace_id
        trace_id_str = format(trace_id, "032x")
        return trace_id_str
    else:
        return "0"
