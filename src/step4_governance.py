"""Micro-Task #4: isolated tracing and an explicitly advisory shield starter."""

import os
from contextlib import contextmanager
from threading import Lock
from uuid import uuid4

from src.foundry_client import emit_trace, trace_to

try:
    from opentelemetry import trace as otel_trace
except ModuleNotFoundError as error:
    if not error.name or not error.name.startswith("opentelemetry"):
        raise
    otel_trace = None


def get_entra_agent_id() -> str:
    identity = os.getenv("ENTRA_AGENT_ID", "entra-agent://ecopulse-green-shifter-01")
    if not identity.startswith("entra-agent://") or not identity.removeprefix(
        "entra-agent://"
    ).strip():
        raise ValueError("ENTRA_AGENT_ID must be a nonempty entra-agent:// identity.")
    return identity


class EcoPulseTracer:
    """Collect local span events, optionally bridging to an installed OTel API."""

    def __init__(self):
        self.entra_agent_id = get_entra_agent_id()
        self.trace_id = uuid4().hex
        self.trace_events: list[dict] = []
        self._lock = Lock()

    def record(self, event: str, **attributes: object) -> None:
        with self._lock:
            item = {
                **attributes, "event": event, "span_name": event,
                "span_id": len(self.trace_events) + 1,
                "trace_id": self.trace_id, "entra_agent_id": self.entra_agent_id,
            }
            self.trace_events.append(item)
        if otel_trace is not None:
            tracer = otel_trace.get_tracer("ecopulse.workshop")
            with tracer.start_as_current_span(event) as span:
                span.add_event(event, attributes={
                    key: value for key, value in item.items()
                    if isinstance(value, (str, int, float, bool))
                })

    @contextmanager
    def activate(self):
        with trace_to(self.record):
            yield self


class PromptShieldFilter:
    """Challenge starter: visibility only, NOT an enforced safety boundary."""

    def check(self, deployment_notes: str) -> bool:
        emit_trace(
            "security.prompt_shield.advisory_only",
            suspicious="system override" in deployment_notes.casefold(),
            reason="Challenge TODO: detect injection and enforce a block before agents.",
        )
        return False
