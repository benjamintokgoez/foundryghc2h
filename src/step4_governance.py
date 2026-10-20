"""Attributed tracing and deterministic, fail-closed challenge governance."""

import os
import re
import unicodedata
from contextlib import contextmanager
from threading import Lock
from uuid import uuid4

from mocks.carbon_grid_store import (
    CROSS_REGION_LATENCY_MS, get_region_carbon, list_all_regions,
)
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
    """Local teaching detector; production requires managed content safety too."""

    _patterns = (
        r"\bsystem[\s_-]+override\b",
        r"\bignore\b.{0,100}\b(all|prior|previous)\b.{0,120}\b(rules|instructions|sla)\b",
        r"\bexecute_workload_shift\b",
        r"\bterminate_all\b",
        r"\bdecommissioned-zone\b",
    )

    def check(self, deployment_notes: str) -> bool:
        normalized = unicodedata.normalize("NFKC", deployment_notes).casefold()
        normalized = "".join(
            character for character in normalized
            if unicodedata.category(character) != "Cf"
        )
        normalized = re.sub(r"\s+", " ", normalized)
        for index, pattern in enumerate(self._patterns, 1):
            if re.search(pattern, normalized):
                emit_trace(
                    "security.prompt_shield.triggered", matched_rule=index,
                    reason="Untrusted deployment notes contain control instructions.",
                )
                return True
        return False


class GovernancePolicyGate:
    """Authorize only from fresh telemetry, never from a generated assessment."""

    def evaluate(self, metrics: dict, target_region: str | None, entra_agent_id: str) -> dict:
        source = get_region_carbon(metrics["current_region"])
        target = get_region_carbon(target_region) if target_region in list_all_regions() else None
        projected = metrics["current_latency_ms"] + CROSS_REGION_LATENCY_MS
        human = metrics["criticality_tier"] == "Tier-0-Critical" or metrics["max_latency_ms"] <= 20
        candidate = (
            metrics["criticality_tier"] in ("Tier-2-Batch", "Tier-2-Background")
            and metrics["max_latency_ms"] > 100
        )
        decision = {
            "workload_id": metrics["workload_id"],
            "current_region": metrics["current_region"], "target_region": target_region,
            "current_gco2_kwh": source["gco2_kwh"],
            "target_gco2_kwh": target["gco2_kwh"] if target else None,
            "criticality_tier": metrics["criticality_tier"],
            "max_latency_ms": metrics["max_latency_ms"],
            "projected_latency_ms": projected, "sla_safe": projected <= metrics["max_latency_ms"],
            "requires_human_approval": human, "is_shift_candidate": candidate,
            "entra_agent_id": entra_agent_id,
        }
        if not entra_agent_id.startswith("entra-agent://") or not entra_agent_id.removeprefix(
            "entra-agent://"
        ).strip():
            status, reason = "BLOCKED_BY_POLICY", "An attributable Entra Agent ID is required."
        elif human:
            status, reason = "PENDING_HUMAN_APPROVAL", "Tier-0 OR <=20ms SLA requires human approval."
        elif projected > metrics["max_latency_ms"]:
            status, reason = "BLOCKED_BY_SLA", "Projected cross-region latency exceeds the SLA."
        elif target_region is None:
            status, reason = "NO_GREEN_TARGET", "No eligible green region was recommended."
        elif (
            target is None or target_region not in ("swedencentral", "norwayeast")
            or target_region == metrics["current_region"] or target["gco2_kwh"] >= 50
        ):
            status, reason = "BLOCKED_BY_POLICY", "Target must be a different, known Nordic green region."
        elif source["gco2_kwh"] <= 300 or not candidate:
            status, reason = "NO_SHIFT_NEEDED", "Source or workload does not meet spatial-shift policy."
        else:
            status, reason = "APPROVED", "Green target, workload tier, identity, and latency verified."
        decision.update(status=status, reason=reason)
        emit_trace(
            "governance.policy", workload_id=metrics["workload_id"],
            status=status, reason=reason,
        )
        return decision
