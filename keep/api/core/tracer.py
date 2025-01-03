from typing import Optional, Sequence

from opentelemetry.context import Context
from opentelemetry.sdk.trace import sampling
from opentelemetry.sdk.trace.sampling import Decision, SamplingResult
from opentelemetry.trace import Link, SpanKind
from opentelemetry.trace.span import TraceState
from opentelemetry.util.types import Attributes


class KeepSampler(sampling.Sampler):
    def __init__(self, parent_sampler=None):
        self.parent_sampler = parent_sampler or sampling.ParentBased(sampling.ALWAYS_ON)
        # Operations we want to exclude from tracing
        self.excluded_operations = {
            "connect",
            "select 1",
            "ping",
            "SELECT 1",
            "ROLLBACK",
            "BEGIN",
            "SELECT keepdb",
            "COMMIT",
        }

    def should_sample(
        self,
        context: Optional["Context"],
        trace_id: int,
        name: str,
        kind: Optional[SpanKind] = None,
        attributes: Attributes = None,
        links: Optional[Sequence["Link"]] = None,
        trace_state: Optional["TraceState"] = None,
    ):
        # For SQL operations
        if kind == SpanKind.CLIENT and name in self.excluded_operations:
            return SamplingResult(Decision.DROP, {}, [])

        # For all other operations, use the parent sampler
        return self.parent_sampler.should_sample(
            context, trace_id, name, kind, attributes, links, trace_state
        )

    def get_description(self):
        return "KeepSampler"
