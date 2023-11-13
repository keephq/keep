import logging
import os

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
from opentelemetry.sdk.trace.sampling import ALWAYS_ON


def setup(app: FastAPI):
    logger = logging.getLogger(__name__)
    # Configure the OpenTelemetry SDK
    service_name = os.environ.get("SERVICE_NAME", "keep-api")
    otlp_collector_endpoint = os.environ.get("OTLP_ENDPOINT", False)
    enable_cloud_trace_exporeter = os.environ.get("CLOUD_TRACE_ENABLED", False)
    metrics_enabled = os.environ.get("METRIC_OTEL_ENABLED", "")
    # to support both grpc and http - for example dynatrace doesn't support grpc
    http_or_grpc = os.environ.get("OTLP_SPAN_EXPORTER", "grpc")
    if http_or_grpc == "grpc":
        OTLPSpanExporter = GRPCOTLPSpanExporter
    else:
        OTLPSpanExporter = HTTPOTLPSpanExporter

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource, sampler=ALWAYS_ON)
    if otlp_collector_endpoint:
        logger.info(f"OTLP endpoint set to {otlp_collector_endpoint}")
        processor = BatchSpanProcessor(
            OTLPSpanExporter(endpoint=otlp_collector_endpoint)
        )
        provider.add_span_processor(processor)
        if metrics_enabled.lower() == "true":
            logger.info("Metrics enabled.")
            reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=otlp_collector_endpoint)
            )
            metric_provider = MeterProvider(resource=resource, metric_readers=[reader])
            metrics.set_meter_provider(metric_provider)

    if enable_cloud_trace_exporeter:
        logger.info("Cloud Trace exporter enabled.")
        processor = BatchSpanProcessor(CloudTraceSpanExporter())
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
