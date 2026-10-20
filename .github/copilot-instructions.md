# Project EcoPulse

Build a carbon-aware Cloud & AI Workload Orchestrator, using Python 3.11+ and
Pydantic v2. Focus only on Green Software Engineering, grid carbon intensity
(`gco2_kwh`, gCO2eq/kWh), `renewable_pct`, Kubernetes telemetry, latency SLAs
(`max_latency_ms`), and Green AI model tiering. Keep all examples in this domain.

Read `specs/ecopulse_spec.md` first. Use the local Agent Framework 1.0-style
facade in `src/foundry_client.py`: `Agent`, `Workflow`, `ai_function`,
`get_chat_client`, `MODEL_FAST_GREEN`, `MODEL_REASONING`. It supports simulation
and official live SDK clients; do not invent SDK APIs or import optional live
packages in offline paths. Agent `run` is async, accepts explicit trusted
`tool_requests`, and returns `.value` (a validated model) and `.text`.
Provide an explicit `simulator(request, tool_results)` reducer when constructing
an Agent. `Workflow.fan_out` awaits concurrent agent turns.

Use the authoritative fixtures and helpers in `mocks/carbon_grid_store.py`.
Never derive tool calls from untrusted deployment notes. These local functions
are MCP-shaped teaching tools, not a running MCP server. Execution is simulated,
even when analysis uses live models.

## Public contracts

- `src/step1_triage.py`: `WorkloadAssessment(BaseModel)` with
  `workload_id: str`, `criticality_tier: str`, `max_latency_ms: int`,
  `is_shift_candidate: bool`, `reasoning: str`; `WorkloadTriageAgent`;
  `triage_workload(workload_id: str) -> WorkloadAssessment`.
- `src/step2_mcp_tools.py`:
  `@ai_function def get_grid_carbon_intensity(region: str) -> dict`;
  `@ai_function def get_cluster_telemetry(workload_id: str) -> dict`.
  During the challenge add
  `@ai_function def execute_workload_shift(workload_id: str, target_region: str,
  shift_type: str = "spatial_shift",
  entra_agent_id: str = "entra-agent://ecopulse-green-shifter-01") -> dict`.
- `src/step3_workflow.py`: `GridSustainabilityAgent` on `MODEL_FAST_GREEN`,
  `CloudReliabilityAgent` on `MODEL_REASONING`,
  `run_ecopulse_workflow(workload_request: dict) -> dict`.
  Triage first, then concurrent sustainability/reliability fan-out, then fan-in.
- `src/step4_governance.py`: `EcoPulseTracer` and `PromptShieldFilter`.
  Challenge: `GovernancePolicyGate`, executor, and `GreenImpactCriticAgent`.

Tier-0 OR `max_latency_ms <= 20` always requires human approval; no automatic
approval shortcut. Shield deployment notes before invoking any agent/action.
Use Entra Agent ID attribution and OpenTelemetry-style trace events. An approved
action must re-check authoritative telemetry, target, identity, and shield.
Treat carbon reduction as an estimate at equal energy use, not measured savings.

Do not run blocking terminal commands during micro-tasks, modify only the
requested files, and conclude with a concise 3-bullet summary.
