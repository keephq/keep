import logging
import os
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from opentelemetry import metrics, trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCOTLPSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPOTLPSpanExporter,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.cloud_trace_propagator import CloudTraceFormatPropagator
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

from keep.api.core.config import config


def get_protocol_from_endpoint(endpoint):
    parsed_url = urlparse(endpoint)
    if parsed_url.scheme == "http":
        return HTTPOTLPSpanExporter
    elif parsed_url.scheme == "grpc":
        return GRPCOTLPSpanExporter
    else:
        raise ValueError(f"Unsupported protocol: {parsed_url.scheme}")


def setup(app: FastAPI):
    logger = logging.getLogger(__name__)
    # Configure the OpenTelemetry SDK
    service_name = os.environ.get(
        "OTEL_SERVICE_NAME", os.environ.get("SERVICE_NAME", "keep-api")
    )
    otlp_collector_endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", os.environ.get("OTLP_ENDPOINT", False)
    )
    otlp_traces_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", None)
    otlp_logs_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", None)
    otlp_metrics_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", None)
    enable_cloud_trace_exporter = config(
        "CLOUD_TRACE_ENABLED", default=False, cast=bool
    )
    metrics_enabled = os.environ.get("METRIC_OTEL_ENABLED", "")

    resource = Resource.create(
        attributes={
            ResourceAttributes.SERVICE_NAME: service_name,
            ResourceAttributes.SERVICE_INSTANCE_ID: f"worker-{os.getpid()}",
        }
    )
    provider = TracerProvider(resource=resource)

    if otlp_collector_endpoint:

        logger.info(f"OTLP endpoint set to {otlp_collector_endpoint}")

        if otlp_traces_endpoint:
            logger.info(f"OTLP Traces endpoint set to {otlp_traces_endpoint}")
            SpanExporter = get_protocol_from_endpoint(otlp_traces_endpoint)
            processor = BatchSpanProcessor(SpanExporter(endpoint=otlp_traces_endpoint))
            provider.add_span_processor(processor)

        if metrics_enabled.lower() == "true" and otlp_metrics_endpoint:
            logger.info(
                f"Metrics enabled. OTLP Metrics endpoint set to {otlp_metrics_endpoint}"
            )
            reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=otlp_metrics_endpoint)
            )
            metric_provider = MeterProvider(resource=resource, metric_readers=[reader])
            metrics.set_meter_provider(metric_provider)

        if otlp_logs_endpoint:
            logger.info(f"OTLP Logs endpoint set to {otlp_logs_endpoint}")

    if enable_cloud_trace_exporter:
        logger.info("Cloud Trace exporter enabled.")
        processor = BatchSpanProcessor(
            CloudTraceSpanExporter(resource_regex="service.*")
        )
        provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)
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
    RequestsInstrumentor().instrument()
    # Enable OpenTelemetry Logging Instrumentation
    LoggingInstrumentor().instrument()
