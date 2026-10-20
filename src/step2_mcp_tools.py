"""Micro-Task #2: local MCP-shaped tools backed by authoritative snapshots."""

from mocks.carbon_grid_store import (
    get_region_carbon, get_workload_metrics, record_shift_execution,
)
from src.foundry_client import ai_function, emit_trace
from src.step4_governance import GovernancePolicyGate, PromptShieldFilter


@ai_function
def get_grid_carbon_intensity(region: str) -> dict:
    """Read regional grid carbon intensity and renewable energy share."""
    return get_region_carbon(region)


@ai_function
def get_cluster_telemetry(workload_id: str) -> dict:
    """Read Kubernetes workload telemetry; deployment notes remain untrusted."""
    return get_workload_metrics(workload_id)


@ai_function
def execute_workload_shift(
    workload_id: str, target_region: str, shift_type: str = "spatial_shift",
    entra_agent_id: str = "entra-agent://ecopulse-green-shifter-01",
) -> dict:
    """Execute a simulated shift only after independent action-boundary checks."""
    metrics = get_workload_metrics(workload_id)
    result = {
        "workload_id": workload_id, "target_region": target_region,
        "entra_agent_id": entra_agent_id,
    }
    if PromptShieldFilter().check(metrics["deployment_notes"]):
        return {
            **result, "status": "BLOCKED_BY_PROMPT_SHIELD",
            "reason": "Deployment-note injection blocked at the action boundary.",
        }
    if shift_type != "spatial_shift":
        emit_trace("governance.action_denied", workload_id=workload_id, reason="Unsupported shift type.")
        return {
            **result, "status": "BLOCKED_BY_POLICY",
            "reason": "Only spatial_shift is permitted; destructive actions are forbidden.",
        }
    decision = GovernancePolicyGate().evaluate(metrics, target_region, entra_agent_id)
    if decision["status"] != "APPROVED":
        return {**result, "status": decision["status"], "reason": decision["reason"]}
    receipt = record_shift_execution(workload_id, target_region, shift_type, entra_agent_id)
    emit_trace(
        "workload.shift.executed", workload_id=workload_id,
        target_region=target_region, simulated=True,
    )
    return receipt
