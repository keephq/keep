from __future__ import annotations

import logging
import os
import threading
from typing import Optional, Sequence, Set

from opentelemetry.context import Context
from opentelemetry.sdk.trace import sampling
from opentelemetry.sdk.trace.sampling import Decision, SamplingResult
from opentelemetry.trace import Link, SpanKind
from opentelemetry.trace.span import TraceState
from opentelemetry.util.types import Attributes


class KeepSampler(sampling.Sampler):
    """
    Drops noisy spans (primarily DB health checks / connection chatter) to reduce trace volume.

    Config:
      - OTEL_SAMPLER_EXCLUDED_OPERATIONS: comma-separated additional exclusions
        Example: "select 1, ping, begin, commit"
      - OTEL_SAMPLER_DEBUG_DROPS: "true"/"false" to enable debug logging of drops
    """

    DEFAULT_EXCLUDED = {
        "connect",
        "ping",
        "select 1",
        "select keepdb",
        "rollback",
        "begin",
        "commit",
    }

    # Kinds where DB-ish spans often appear across libs/frameworks.
    # Note: Some frameworks leave kind as None.
    EXCLUDED_KINDS = {SpanKind.CLIENT, SpanKind.INTERNAL, None}

    def __init__(
        self,
        parent_sampler: Optional[sampling.Sampler] = None,
        excluded_operations: Optional[Set[str]] = None,
    ):
        if parent_sampler is not None and not isinstance(parent_sampler, sampling.Sampler):
            raise TypeError(f"parent_sampler must be a Sampler, got {type(parent_sampler)}")

        self.parent_sampler = parent_sampler or sampling.ParentBased(sampling.ALWAYS_ON)

        # Logging and counters
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._dropped_count = 0
        self._debug_drops = os.getenv("OTEL_SAMPLER_DEBUG_DROPS", "false").strip().lower() in {
            "1", "true", "yes", "y", "on"
        }

        # Build exclusions (normalized)
        base = (excluded_operations or self.DEFAULT_EXCLUDED.copy())

        env_exclusions = os.getenv("OTEL_SAMPLER_EXCLUDED_OPERATIONS", "").strip()
        if env_exclusions:
            base.update({x.strip() for x in env_exclusions.split(",") if x.strip()})

        self.excluded_operations = {self._norm(x) for x in base if isinstance(x, str) and x.strip()}

        # Helpful but not noisy
        self.logger.info(
            "KeepSampler initialized",
            extra={
                "excluded_operations_count": len(self.excluded_operations),
                "parent_sampler": self.parent_sampler.get_description(),
            },
        )

    @staticmethod
    def _norm(s: str) -> str:
        # normalize whitespace + case
        return " ".join(s.strip().lower().split())

    @staticmethod
    def _looks_like_select_one(sql: str) -> bool:
        """
        Match common health check patterns cheaply.
        Examples: "SELECT 1", "SELECT 1;", "SELECT 1 FROM DUAL", "select 1 /* ping */"
        """
        s = KeepSampler._norm(sql)

        # Quick exact matches
        if s == "select 1":
            return True

        # Common prefixes
        if s.startswith("select 1;"):
            return True
        if s.startswith("select 1 from"):
            return True

        # Some libs stick it in attributes with trailing comments
        # "select 1 /* ping */"
        if s.startswith("select 1 "):
            return True

        return False

    def _should_exclude(
        self,
        name: str,
        kind: Optional[SpanKind],
        attributes: Optional[Attributes],
    ) -> bool:
        # Only filter selected kinds. This avoids accidentally dropping HTTP server spans, etc.
        if kind not in self.EXCLUDED_KINDS:
            return False

        norm_name = self._norm(name or "")

        # Direct operation name matching
        if norm_name in self.excluded_operations:
            return True

        # Name may contain the SQL statement in some instrumentations
        if self._looks_like_select_one(norm_name):
            return True

        # Attribute-based detection (more reliable than span name sometimes)
        if attributes:
            stmt = attributes.get("db.statement")
            if isinstance(stmt, str) and stmt:
                if self._looks_like_select_one(stmt):
                    return True
                if self._norm(stmt) in self.excluded_operations:
                    return True

            op = attributes.get("db.operation")
            if isinstance(op, str) and self._norm(op) in self.excluded_operations:
                return True

            # Sometimes "connect"/"ping" appear as "db.operation" or "db.statement"
            # covered by the checks above.

        return False

    def should_sample(
        self,
        context: Optional[Context],
        trace_id: int,
        name: str,
        kind: Optional[SpanKind] = None,
        attributes: Attributes = None,
        links: Optional[Sequence[Link]] = None,
        trace_state: Optional[TraceState] = None,
    ) -> SamplingResult:
        if self._should_exclude(name, kind, attributes):
            with self._lock:
                self._dropped_count += 1

            if self._debug_drops:
                self.logger.debug(
                    "Dropping span (excluded operation)",
                    extra={
                        "span_name": name,
                        "span_kind": kind.name if kind else None,
                        "trace_id": f"{trace_id:032x}",
                    },
                )

            # Preserve trace_state for propagation (don’t break downstream context)
            return SamplingResult(
                decision=Decision.DROP,
                attributes={},
                trace_state=trace_state,
            )

        # Delegate everything else to parent sampler
        return self.parent_sampler.should_sample(
            context, trace_id, name, kind, attributes, links, trace_state
        )

    def get_description(self) -> str:
        with self._lock:
            dropped = self._dropped_count
        return f"KeepSampler(excluded_ops={len(self.excluded_operations)}, dropped={dropped})"