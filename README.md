# EcoPulse Agent Workshop

## Building Sustainable Cloud Agents with Microsoft Foundry, Microsoft Agent Framework & GitHub Copilot

Welcome to **Project EcoPulse**: a two-hour, hands-on journey into carbon-aware
cloud operations and Green AI.
Build a triage agent, wire MCP-shaped telemetry tools, fan out across specialist
agents, then govern a safe workload shift in a 30-minute challenge.

## Quickstart: completely offline after dependency installation

Use **Python 3.11+**. No cloud account, external API key, or live SDK is needed.

```bash
python3.11 -m venv .venv  # or another installed Python 3.11+ interpreter
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cp .env.example .env
python run_challenge.py --check-env
python run_challenge.py
python -m pytest -q
```

The starter intentionally has no step modules; its scoreboard is **0% Starter
State**. Tests for unavailable steps skip until their checkpoint exists.
Dependency installation time depends on network and wheel caching; preinstall
before the session. With installed dependencies, simulation uses no network.

## Workshop checkpoints

| Branch | When | State |
| --- | --- | --- |
| `main` | Pre-session clone | Starter, SDK facade, fixtures, runner and contracts |
| `step-1` | Micro-Task #1, 00:26 | Pydantic triage agent |
| `step-2` | Micro-Task #2, 00:48 | Registered telemetry and grid tools |
| `step-3` | Micro-Task #3, 01:06 | Concurrent multi-agent analysis |
| `basecamp` | Challenge start, 01:21 | Tracing and a deliberately unenforced shield |
| `step-4` | Alias for `basecamp` | Same commit as `basecamp` |
| `solution-complete` | Debrief, 01:48 | Executor, approval gate, shield and critic |

```bash
git checkout step-1
git checkout step-2
git checkout step-3
git checkout basecamp
git checkout solution-complete
```

At each checkpoint: **Fire** a workload, **Listen** to the recommendation,
**Inspect** structured output and traces. Begin the final mission in
[CHALLENGE.md](CHALLENGE.md). The normative contract is
[specs/ecopulse_spec.md](specs/ecopulse_spec.md).

## Architecture and trust

```text
Authoritative telemetry -> Prompt Shield (enforced in solution)
    -> WorkloadTriageAgent [FAST_GREEN]
    -> concurrent fan-out:
         GridSustainabilityAgent [FAST_GREEN]
         CloudReliabilityAgent [REASONING]
    -> fan-in GreenShiftPlan
    -> deterministic GovernancePolicyGate
    -> GreenShiftExecutorAgent -> guarded action -> in-memory receipt
    -> GreenImpactCriticAgent -> estimates + attributed trace events
```

`src/foundry_client.py` is a small workshop adapter over the **official Microsoft
Agent Framework Python SDK** (`agent-framework-core`, a required dependency).
Every agent turn uses the SDK's `Agent`, including offline, deterministic critic,
and authoritative action-receipt turns. Simulation supplies a local chat client
with an explicit domain reducer; it does not simulate the agent framework itself.
The adapter preserves the workshop's async `Agent.run`, validated `.value` /
`.text` response, and `@ai_function` interface using SDK tools.
Tool names and arguments come exclusively from explicit, trusted application
requests; tools are not offered to the model for autonomous selection.
`Workflow.fan_out` uses `asyncio.gather` to await real framework agents
concurrently; this helper is application orchestration, not an SDK workflow graph.
Routine reasoning uses `MODEL_FAST_GREEN`; SLA reasoning uses `MODEL_REASONING`.

The tools are local **MCP-shaped** functions, not an MCP transport/server.
Actions always simulate Kubernetes shifts; no cluster is contacted. The local
Prompt Shield models a Foundry defense but is not the managed service. Entra
Agent IDs are audit labels here, not an authentication implementation.
OpenTelemetry-style events work offline; installing `opentelemetry-sdk` bridges
events to an externally configured tracer provider (no exporter is enabled here).
Before `solution-complete`, plans are advisory and the challenge scoreboard
does not claim the four scenario assertions pass.

## Optional live analysis

```bash
# Agent Framework core is installed by requirements.txt.
# Framework provider clients for live analysis:
python -m pip install agent-framework-openai==1.17.0
# Foundry project access additionally:
python -m pip install azure-ai-projects azure-identity
# Optional OpenTelemetry bridge:
# python -m pip install opentelemetry-sdk
```

Set `ECOPULSE_MODE=live` in `.env`, and configure **one** provider. Precedence is
Foundry project, Azure OpenAI, OpenAI, then GitHub Models.

| Provider | Configuration |
| --- | --- |
| Microsoft Foundry | `AZURE_AI_PROJECT_ENDPOINT` + `az login` / DefaultAzureCredential and project permissions |
| Azure OpenAI | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`; optional `AZURE_OPENAI_API_VERSION` |
| OpenAI | `OPENAI_API_KEY`; optional `OPENAI_BASE_URL` |
| GitHub Models | `GITHUB_TOKEN` with model access |

For non-Foundry providers, **remove** the example `AZURE_AI_PROJECT_ENDPOINT`
from `.env`. Replace `MODEL_FAST_GREEN` and `MODEL_REASONING` with deployed
model identifiers available to your provider; the defaults are workshop labels
and not universally available models. Live providers must support structured
output. Foundry wraps `AIProjectClient.get_openai_client()` with the framework's
Responses client; the other providers use the framework's OpenAI/Azure chat
clients. Model inference runs through a framework agent, not direct completion
calls from workshop code.
Errors, refusals, unsupported models, and missing credentials surface explicitly;
live mode never quietly becomes simulation. The larger `agent-framework`
meta-package is unnecessary: the official core distribution supplies Agent and
tool APIs, with `agent-framework-openai` supplying optional live provider clients.

Model analysis is probabilistic in live mode. Authorization, action arguments,
receipts, critic arithmetic, and SLA enforcement stay in deterministic trusted
code. The four reproducible reference scenarios are verified in simulation.
Do not submit private deployment notes to an external provider.

## Copy-ready presentation prompts

[CHALLENGE.md](CHALLENGE.md) contains prompts for starter readiness, `step-1`,
`step-2`, `step-3`, `basecamp` / `step-4`, and the complete challenge, with expected
states and verification criteria. Copy the prompt blocks into your slides and
paste them into Copilot in sequence to build from this starter.
Published checkpoint branches are snapshots; this change updates the current
branch only and does not rewrite older checkpoints.

## Reuse and license

This workshop is available under the [MIT License](LICENSE). You can use, modify,
and redistribute it, including adapting it for your own workshops. Retain the
license and copyright notice when redistributing copies or substantial portions.

## Publish when ready

The generator leaves `main` checked out with every local checkpoint committed.
If no remote exists:

```bash
gh repo create ecopulse-agent-workshop --public --source=. --remote=origin --push
git push origin --all
```

If a remote already exists, inspect `git remote -v` before pushing. Publishing is
an explicit facilitator action; repository generation does not publish anything.
