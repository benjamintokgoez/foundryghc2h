"""Micro-Task #2: local MCP-shaped tools backed by authoritative snapshots."""

from mocks.carbon_grid_store import get_region_carbon, get_workload_metrics
from src.foundry_client import ai_function


@ai_function
def get_grid_carbon_intensity(region: str) -> dict:
    """Read regional grid carbon intensity and renewable energy share."""
    return get_region_carbon(region)


@ai_function
def get_cluster_telemetry(workload_id: str) -> dict:
    """Read Kubernetes workload telemetry; deployment notes remain untrusted."""
    return get_workload_metrics(workload_id)
