"""Workshop facade backed by the official Microsoft Agent Framework.

Analysis uses official framework provider clients in live mode. Tool selection stays in
trusted application code in BOTH modes; deployment notes never select tools.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AsyncExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import ParamSpec, TypeVar, get_type_hints

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, create_model
from agent_framework import (
    Agent as FrameworkAgent, BaseChatClient, ChatResponse, Message,
    tool as framework_tool,
)

load_dotenv()

MODEL_FAST_GREEN = "phi-4-green"
MODEL_REASONING = "o4-mini-reasoning"
ToolResults = dict[str, list[dict]]
TraceSink = Callable[..., None]
_trace_sink: ContextVar[TraceSink | None] = ContextVar("ecopulse_trace_sink", default=None)
P = ParamSpec("P")
R = TypeVar("R")

__all__ = [
    "Agent", "Workflow", "ai_function", "get_chat_client",
    "MODEL_FAST_GREEN", "MODEL_REASONING",
]


def emit_trace(event: str, **attributes: object) -> None:
    """Send telemetry to the current workflow's isolated trace sink."""
    sink = _trace_sink.get()
    if sink is not None:
        sink(event, **attributes)


@contextmanager
def trace_to(sink: TraceSink):
    token = _trace_sink.set(sink)
    try:
        yield
    finally:
        _trace_sink.reset(token)


def ai_function(function: Callable[P, R]) -> Callable[P, R]:
    """Register a callable with a validated Pydantic argument schema."""
    signature = inspect.signature(function)
    hints = get_type_hints(function)
    fields = {
        name: (
            hints.get(name, str),
            ... if parameter.default is inspect.Parameter.empty else parameter.default,
        )
        for name, parameter in signature.parameters.items()
    }
    arguments_model = create_model(
        f"{function.__name__}Arguments", __config__=ConfigDict(extra="forbid"), **fields
    )

    @wraps(function)
    def validated(*args: P.args, **kwargs: P.kwargs) -> R:
        bound = signature.bind(*args, **kwargs)
        arguments = arguments_model.model_validate(bound.arguments)
        return function(**arguments.model_dump())

    validated.__ai_function__ = True
    validated.__tool_schema__ = {
        "name": function.__name__, "description": inspect.getdoc(function) or "",
        "parameters": arguments_model.model_json_schema(),
    }
    validated.__framework_tool__ = framework_tool(validated, schema=arguments_model)
    return validated


def _mode() -> str:
    mode = os.getenv("ECOPULSE_MODE", "simulation").strip().lower()
    if mode not in {"simulation", "live"}:
        raise ValueError("ECOPULSE_MODE must be simulation or live.")
    return mode


def _provider() -> str:
    if os.getenv("AZURE_AI_PROJECT_ENDPOINT"):
        if "your-foundry-project" in os.environ["AZURE_AI_PROJECT_ENDPOINT"]:
            raise ValueError(
                "Replace AZURE_AI_PROJECT_ENDPOINT, or unset it to use another provider."
            )
        return "foundry"
    if os.getenv("AZURE_OPENAI_ENDPOINT"):
        if not os.getenv("AZURE_OPENAI_API_KEY"):
            raise ValueError("AZURE_OPENAI_API_KEY is required for Azure OpenAI mode.")
        return "azure_openai"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("GITHUB_TOKEN"):
        return "github"
    raise ValueError(
        "Live mode requires AZURE_AI_PROJECT_ENDPOINT, Azure OpenAI configuration, "
        "OPENAI_API_KEY, or GITHUB_TOKEN. Use ECOPULSE_MODE=simulation for offline work."
    )


@dataclass(frozen=True)
class ChatClient:
    model: str
    mode: str
    provider: str = "simulation"

    async def complete(
        self, instructions: str, payload: dict, results: ToolResults,
        response_format: type[BaseModel], *, agent_name: str | None = None,
    ) -> BaseModel:
        """Run live analysis through an official framework agent, never raw completions."""
        try:
            from agent_framework.openai import OpenAIChatClient, OpenAIChatCompletionClient
            from openai import AsyncAzureOpenAI, AsyncOpenAI
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "Live mode requires: pip install agent-framework-openai==1.17.0"
            ) from error

        content = json.dumps({"request": payload, "trusted_tool_results": results})
        async with AsyncExitStack() as stack:
            if self.provider == "foundry":
                try:
                    from azure.ai.projects.aio import AIProjectClient
                    from azure.identity.aio import DefaultAzureCredential
                except ModuleNotFoundError as error:
                    raise RuntimeError(
                        "Foundry mode requires: pip install azure-ai-projects azure-identity"
                    ) from error
                credential = await stack.enter_async_context(DefaultAzureCredential())
                project = await stack.enter_async_context(AIProjectClient(
                    endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"], credential=credential,
                ))
                client = await stack.enter_async_context(project.get_openai_client())
                framework_client = OpenAIChatClient(
                    model=self.model, async_client=client,
                )
            elif self.provider == "azure_openai":
                client = await stack.enter_async_context(AsyncAzureOpenAI(
                    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                    api_key=os.environ["AZURE_OPENAI_API_KEY"],
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
                    timeout=45.0, max_retries=1,
                ))
                framework_client = OpenAIChatCompletionClient(
                    model=self.model, async_client=client,
                )
            else:
                client = await stack.enter_async_context(AsyncOpenAI(
                    api_key=os.environ[
                        "GITHUB_TOKEN" if self.provider == "github" else "OPENAI_API_KEY"
                    ],
                    base_url=(
                        "https://models.github.ai/inference" if self.provider == "github"
                        else os.getenv("OPENAI_BASE_URL")
                    ),
                    timeout=45.0, max_retries=1,
                ))
                framework_client = OpenAIChatCompletionClient(
                    model=self.model, async_client=client,
                )
            return await _run_framework(
                framework_client, instructions, content, response_format,
                name=agent_name,
            )


class _SimulatorClient(BaseChatClient):
    """Offline transport: domain reducers still run inside the real framework."""

    def __init__(self, reducer: Callable[[], dict | BaseModel]):
        super().__init__()
        self.reducer = reducer

    async def _inner_get_response(self, *, messages, stream, options, **kwargs):
        if stream:
            raise ValueError("The workshop simulator supports non-streaming turns only.")
        value = self.reducer()
        text = value.model_dump_json() if isinstance(value, BaseModel) else json.dumps(value)
        return ChatResponse(messages=Message("assistant", [text]))


async def _run_framework(client, instructions, content, response_format, *, name=None):
    # Application-owned tools are deliberately NOT advertised to the model.
    agent = FrameworkAgent(client=client, instructions=instructions, name=name)
    response = await agent.run(content, options={
        "response_format": response_format,
    })
    if response.value is not None:
        return response_format.model_validate(response.value)
    if not response.text:
        raise RuntimeError("The live model refused or omitted the structured response.")
    return response_format.model_validate_json(response.text)


def get_chat_client(model: str = MODEL_FAST_GREEN) -> ChatClient:
    """Resolve a model tier; simulation never imports optional live integrations."""
    mode = _mode()
    if mode == "simulation":
        return ChatClient(model=model, mode=mode)
    resolved = {
        MODEL_FAST_GREEN: os.getenv("MODEL_FAST_GREEN", "Phi-4"),
        MODEL_REASONING: os.getenv("MODEL_REASONING", "o4-mini"),
    }.get(model, model)
    return ChatClient(model=resolved, mode=mode, provider=_provider())


@dataclass
class AgentResponse:
    value: BaseModel
    tool_results: ToolResults = field(default_factory=dict)

    @property
    def text(self) -> str:
        return self.value.model_dump_json()


class Agent:
    """Shared async agent contract with schema validation and real local tools.

    ``simulator`` is an explicit domain reducer, never a guessed model response.
    ``authoritative_tool`` bypasses generation for an action receipt.
    """

    def __init__(
        self, *, name: str, client: ChatClient, instructions: str,
        response_format: type[BaseModel], tools: Sequence[Callable] = (),
        simulator: Callable[[dict, ToolResults], dict | BaseModel],
    ):
        self.name = name
        self.client = client
        self.instructions = instructions
        self.response_format = response_format
        self.simulator = simulator
        self.tools: dict[str, Callable] = {}
        for function in tools:
            if not getattr(function, "__ai_function__", False):
                raise TypeError("Tools must be decorated with @ai_function.")
            if function.__name__ in self.tools:
                raise ValueError(f"Duplicate tool: {function.__name__}")
            self.tools[function.__name__] = function

    async def run(
        self, request: dict | str, *,
        tool_requests: Sequence[tuple[str, dict]] = (),
        authoritative_tool: str | None = None,
        deterministic: bool = False,
    ) -> AgentResponse:
        payload = json.loads(request) if isinstance(request, str) else request
        emit_trace("agent.turn", agent=self.name, model=self.client.model)
        results: ToolResults = {}
        for name, arguments in tool_requests:
            if name not in self.tools:
                raise ValueError(f"Unregistered tool: {name}")
            emit_trace("tool.call", agent=self.name, tool=name)
            result = await self.tools[name].__framework_tool__.invoke(
                arguments=arguments, skip_parsing=True,
            )
            if not isinstance(result, dict):
                raise TypeError(f"{name} must return a dictionary.")
            results.setdefault(name, []).append(result)
        if authoritative_tool is not None:
            if len(results.get(authoritative_tool, [])) != 1:
                raise ValueError("An authoritative action must return exactly one receipt.")
            reducer = lambda: results[authoritative_tool][0]
        elif self.client.mode == "simulation" or deterministic:
            reducer = lambda: self.simulator(payload, results)
        else:
            value = await self.client.complete(
                self.instructions, payload, results, self.response_format,
                agent_name=self.name,
            )
            return AgentResponse(value, results)
        value = await _run_framework(
            _SimulatorClient(reducer), self.instructions,
            json.dumps({"request": payload, "trusted_tool_results": results}),
            self.response_format, name=self.name,
        )
        return AgentResponse(self.response_format.model_validate(value), results)


class Workflow:
    """Async orchestration facade; fan-out really runs tasks concurrently."""

    def __init__(self, runner: Callable[[dict], Awaitable[dict]]):
        self.runner = runner

    async def run(self, request: dict) -> dict:
        return await self.runner(request)

    @staticmethod
    async def fan_out(*turns: Awaitable[AgentResponse]) -> list[AgentResponse]:
        return list(await asyncio.gather(*turns))
