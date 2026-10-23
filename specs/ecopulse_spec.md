# Project EcoPulse engineering specification

## Mission and units

Recommend carbon-aware spatial shifts for cloud and AI workloads while preserving
reliability, security, and human oversight. Grid intensity uses `gco2_kwh`
(gCO2eq/kWh); renewable share uses `renewable_pct` (0-100).

| Signal | Policy |
| --- | --- |
| `< 50 gCO2eq/kWh` | Green Target |
| `> 300 gCO2eq/kWh` | High Carbon Source |
| `Tier-0-Critical` **or** `max_latency_ms <= 20` | Human-in-the-Loop approval required |
| `Tier-2-Batch` / `Tier-2-Background`, `max_latency_ms > 100` | Prime spatial-shift candidates |

The candidate targets are `swedencentral` and `norwayeast`. Prefer the lowest
intensity eligible region. Every cross-region shift adds 28ms to current latency.
Exactly 50 is not a Green Target; exactly 300 is not a High Carbon Source.
Never execute if projected latency exceeds the workload SLA.

## Authoritative telemetry

`mocks/carbon_grid_store.py` contains three regional snapshots and four workloads:
`ai-embedding-batch`, `cdn-asset-sync`, `checkout-api`, and `core-auth`.
Only the workload identifier is accepted from workflow callers; re-read metrics
from the telemetry store. Deployment notes are untrusted data, not instructions.
Snapshots are copied; executing a simulated shift appends an audit receipt but
does not mutate the fixtures. Repeated runs remain reproducible.

## Agent architecture

Use the official Microsoft Agent Framework Python SDK for every agent turn.
`src/foundry_client.py` adapts its Agent, tool, and chat-client APIs to the
workshop contracts; it must not implement an independent agent runtime.
Simulation uses the real SDK with a local deterministic chat client and no
network access. Live inference uses framework provider clients. Trusted tool
requests are executed through SDK tools and are never selected by model output.
The local Workflow helper coordinates concurrent SDK agents with
`asyncio.gather`; it does not claim to be a framework workflow graph.

1. `WorkloadTriageAgent` produces a Pydantic `WorkloadAssessment`.
2. Concurrent fan-out: `GridSustainabilityAgent` selects a green region, while
   `CloudReliabilityAgent` checks the 28ms latency increment.
3. Fan-in produces a `GreenShiftPlan`. Before the challenge this is advisory only.
4. The reference solution applies a deterministic policy gate, calls the
   `GreenShiftExecutorAgent` action tool, and computes critic metrics.

Use `MODEL_FAST_GREEN = "phi-4-green"` for routine analysis and
`MODEL_REASONING = "o4-mini-reasoning"` for SLA reasoning. Live deployments are
resolved from environment variables; model output never authorizes an action.
`green_ai_score` is the percentage of planned agent roles assigned to the fast
tier (0-100), a teaching proxy, not a hardware energy measurement.

## Governance and trust boundary

- Attribute every action, approval request, and trace to an `ENTRA_AGENT_ID`.
  The local URI is audit metadata, not an authenticated Entra credential.
- Tier-0 **or** an SLA of 20ms or less returns `PENDING_HUMAN_APPROVAL`.
  The workshop does not implement a human approval/continuation service.
- Teach Foundry Prompt Shields using a deterministic local `PromptShieldFilter`.
  In the solution, detect the poisoned `core-auth` manifest before agent/action
  invocation; return `BLOCKED_BY_PROMPT_SHIELD` and record
  `security.prompt_shield.triggered`. Never implement or call `terminate_all`.
- The local detector is a teaching defense, not a production Prompt Shields
  service or a complete injection classifier. A real deployment must add managed
  content safety, workload identity, authorization, and Kubernetes admission rules.
- Allow only `spatial_shift`, known green regions, attributed identities, and
  policy-approved fresh telemetry at the action boundary.
- Record `agent.turn`, `tool.call`, and `carbon.saved_estimate` events with an
  isolated `EcoPulseTracer`. Optionally bridge to a configured OpenTelemetry SDK.

## Expected reference outcomes

| Workload | Required status | Additional invariant |
| --- | --- | --- |
| `ai-embedding-batch` | `SHIFT_EXECUTED` | Nordic target, estimated reduction > 80% |
| `cdn-asset-sync` | `SHIFT_EXECUTED` | Nordic target |
| `checkout-api` | `PENDING_HUMAN_APPROVAL` | Entra attribution; no action |
| `core-auth` | `BLOCKED_BY_PROMPT_SHIELD` | Shield event; no action |

Estimated reduction is `100 * (source_intensity - target_intensity) /
source_intensity`, assuming equal workload energy consumption. Do not report
absolute emissions savings without workload energy data.
