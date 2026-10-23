"""Branch-aware EcoPulse scoreboard: infrastructure errors are never hidden."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEP_FILES = (
    "step1_triage.py", "step2_mcp_tools.py", "step3_workflow.py", "step4_governance.py",
)
SCENARIOS = (
    ("ai-embedding-batch", "SHIFT_EXECUTED", "Add the guarded executor and action tool."),
    ("cdn-asset-sync", "SHIFT_EXECUTED", "Execute a safe Nordic spatial shift."),
    ("checkout-api", "PENDING_HUMAN_APPROVAL", "Enforce the Tier-0 OR <=20ms approval gate."),
    ("core-auth", "BLOCKED_BY_PROMPT_SHIELD", "Enforce the deployment-note shield before agents."),
)


def output(message: str, *, success: bool = True) -> None:
    try:
        from rich.console import Console
    except ModuleNotFoundError as error:
        if error.name != "rich":
            raise
        if sys.stdout.isatty() and "NO_COLOR" not in os.environ:
            color = "32" if success else "33"
            print(f"\033[{color}m{message}\033[0m")
        else:
            print(message)
    else:
        Console(highlight=False, markup=False).print(
            message, style="green" if success else "yellow"
        )


def workshop_progress() -> int:
    present = [(ROOT / "src" / filename).is_file() for filename in STEP_FILES]
    for index, exists in enumerate(present):
        if not exists:
            if any(present[index + 1:]):
                raise RuntimeError("Checkpoint modules are out of order; restore the missing step.")
            return index
    return len(STEP_FILES)


def check_environment() -> None:
    if sys.version_info < (3, 11):
        raise RuntimeError("EcoPulse requires Python 3.11 or later.")
    for package in ("pydantic", "pytest", "dotenv", "agent_framework"):
        if importlib.util.find_spec(package) is None:
            raise RuntimeError(f"Missing {package}: python -m pip install -r requirements.txt")
    from pydantic.version import VERSION
    from src.foundry_client import get_chat_client

    if int(VERSION.split(".")[0]) != 2:
        raise RuntimeError("EcoPulse requires Pydantic v2.")
    client = get_chat_client()
    if client.mode == "live" and importlib.util.find_spec("agent_framework_openai") is None:
        raise RuntimeError(
            "Live mode requires: python -m pip install agent-framework-openai==1.17.0"
        )
    if client.provider == "foundry":
        # Import checks do not make an external request or expose credentials.
        importlib.import_module("azure.ai.projects.aio")
        importlib.import_module("azure.identity.aio")
    output("✅ EcoPulse Workshop Environment Ready!")
    output(f"Mode: {client.mode}; Python {sys.version_info.major}.{sys.version_info.minor}")
    if client.mode == "live":
        output("Configuration checked only; live authentication/connectivity not yet exercised.")


def scenario_passes(workload_id: str, expected: str, result: dict) -> bool:
    if result.get("status") != expected or result.get("workload_id") != workload_id:
        return False
    if expected == "SHIFT_EXECUTED":
        if result.get("target_region") not in ("swedencentral", "norwayeast"):
            return False
        if workload_id == "ai-embedding-batch":
            if result.get("estimated_co2_reduction_pct", 0) <= 80:
                return False
    if expected == "PENDING_HUMAN_APPROVAL" and not result.get("entra_agent_id"):
        return False
    if expected == "BLOCKED_BY_PROMPT_SHIELD":
        return any(
            event.get("event") == "security.prompt_shield.triggered"
            for event in result.get("trace_events", [])
        )
    return True


def run_scoreboard() -> int:
    progress = workshop_progress()
    labels = (
        "[🌱 0% Starter State]",
        "[🌿 25% — Step 1 Complete: WorkloadTriageAgent Ready]",
        "[🌲 50% — Step 2 Complete: MCP Telemetry & Carbon Tools Wired]",
        "[🌳 75% — Step 3 Complete: Concurrent Multi-Agent Workflow Active]",
        "[🌍 Basecamp]",
    )
    output(labels[progress])
    if progress < 3:
        for number, (_, _, hint) in enumerate(SCENARIOS, 1):
            output(f"Scenario {number}: WAITING — {hint}", success=False)
        return 0

    workflow = importlib.import_module("src.step3_workflow")
    tools = importlib.import_module("src.step2_mcp_tools")
    complete = hasattr(workflow, "GreenShiftExecutorAgent") and hasattr(
        tools, "execute_workload_shift"
    )
    passed = 0
    for number, (workload_id, expected, hint) in enumerate(SCENARIOS, 1):
        result = workflow.run_ecopulse_workflow({"workload_id": workload_id})
        ok = scenario_passes(workload_id, expected, result)
        passed += int(ok)
        badge = "✅ PASS" if ok else ("❌ FAIL" if complete else "⏳ WAITING")
        output(
            f"Scenario {number} ({workload_id}): {badge} — {result['status']}"
            + ("" if ok else f" | {hint}"),
            success=ok,
        )
    if progress == 4 and not complete:
        output(
            "🌍 BASECAMP REACHED (100% Presentation Tasks Complete — "
            "Ready for the 30-Min Challenge!)"
        )
        output(
            "Scenarios 1 & 2: Analysis Ready (Waiting for GreenShiftExecutorAgent "
            "& execute_workload_shift tool)"
        )
        output(
            "Scenarios 3 & 4: Waiting for Tier-0 SLA Human Approval Gate "
            "& PromptShield Block Enforcement"
        )
    if passed == 4:
        output("[🏆 Challenge Complete: 4/4 PASSED 🌱]")
        output("4/4 SCENARIOS PASSED 🌱")
    elif complete:
        output(f"{passed}/4 SCENARIOS PASSED — inspect the failed invariants.", success=False)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-env", action="store_true")
    args = parser.parse_args()
    if args.check_env:
        check_environment()
        return 0
    return run_scoreboard()


if __name__ == "__main__":
    raise SystemExit(main())
