# EcoPulse Agent Workshop

## Building Sustainable Cloud Agents with Microsoft Foundry, Microsoft Agent Framework & GitHub Copilot

Welcome to **Project EcoPulse**: a two-hour, hands-on journey into carbon-aware
cloud operations and Green AI.
Build a triage agent, wire MCP-shaped telemetry tools, fan out across specialist
agents, then govern a safe workload shift in a 30-minute challenge.

## Quickstart: completely offline after dependency installation

Use **Python 3.11+**. No cloud account, external API key, or live SDK is needed.

```bash
git clone https://github.com/benjamintokgoez/foundryghc2h.git
cd foundryghc2h
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
| `solution-complete` | Wrap-up, 01:51 | Executor, approval gate, shield and critic |

```bash
git checkout step-1
git checkout step-2
git checkout step-3
git checkout basecamp
git checkout solution-complete
```

Copilot creates the step files as untracked files, and Git refuses to switch to a
checkpoint that contains the same files. Stash first, then switch; your own
attempt stays recoverable with `git stash pop`:

```bash
git stash --include-untracked
git checkout basecamp
```

At each micro-task: **Fire** the prompt from [PROMPTS.md](PROMPTS.md) in Copilot
Agent Mode, **Listen** to the session while Copilot builds, then **Inspect** the
scoreboard, structured output and traces. Begin the final mission in
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

`src/foundry_client.py` provides an intentionally small **Agent Framework
1.0-style compatibility facade**, not a vendored or drop-in full SDK.
`Agent.run` is async, invokes registered `@ai_function` tools selected by trusted
application code, and validates Pydantic `response_format` schemas.
`Workflow.fan_out` uses real concurrent async turns. Offline reducers are
explicit domain logic, not canned LLM strings. Routine reasoning uses
`MODEL_FAST_GREEN`; SLA reasoning uses `MODEL_REASONING`.

The tools are local **MCP-shaped** functions, not an MCP transport/server.
Actions always simulate Kubernetes shifts; no cluster is contacted. The local
Prompt Shield models a Foundry defense but is not the managed service. Entra
Agent IDs are audit labels here, not an authentication implementation.
OpenTelemetry-style events work offline; installing `opentelemetry-sdk` bridges
events to an externally configured tracer provider (no exporter is enabled here).
Before `solution-complete`, plans are advisory and the challenge scoreboard
does not claim the four scenario assertions pass.

## Why agents here?

Honestly: with four tidy fixtures, plain if-statements would do. The offline
reducers in this repo are deterministic Python on purpose, so the workshop is
reproducible and needs no model. We use agents because production telemetry is
messier (free-text notes, missing or wrong tier labels, trade-offs no rule list
covers), and the pattern we practice holds there: the model advises, trusted code
decides. `GovernancePolicyGate`, the shield, the receipt and the CO2 arithmetic are
deterministic, and model output never authorizes an action.

## Optional live analysis

```bash
python -m pip install openai
# Foundry additionally:
python -m pip install azure-ai-projects azure-identity
# Optional full SDK for further exercises and real telemetry:
# python -m pip install agent-framework opentelemetry-sdk
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
output. Foundry uses official `AIProjectClient.get_openai_client()` and the
Responses API; the other providers use official OpenAI structured chat clients.
Errors, refusals, unsupported models, and missing credentials surface explicitly;
live mode never quietly becomes simulation. The optional `agent-framework`
package is not needed by this deliberately narrow SDK-backed facade.

Model analysis is probabilistic in live mode. Authorization, action arguments,
receipts, critic arithmetic, and SLA enforcement stay in deterministic trusted
code. The four reproducible reference scenarios are verified in simulation.
Do not submit private deployment notes to an external provider.

## Reuse and license

This workshop is available under the [MIT License](LICENSE). You can use, modify,
and redistribute it, including adapting it for your own workshops. Retain the
license and copyright notice when redistributing copies or substantial portions.

## Publishing your own copy

The reference copy of this workshop lives at
<https://github.com/benjamintokgoez/foundryghc2h>. To publish an adapted copy,
push every checkpoint branch, not only `main`:

```bash
gh repo create <your-repo-name> --public --source=. --remote=origin --push
git push origin --all
```

If a remote already exists, inspect `git remote -v` before pushing.
