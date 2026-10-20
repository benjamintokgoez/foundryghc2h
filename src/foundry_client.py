"""Small Agent Framework 1.0-style teaching facade, not a replacement SDK.

Analysis uses official OpenAI/Azure SDKs in live mode. Tool selection stays in
trusted application code in BOTH modes; deployment notes never select tools.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from collections.abc import Awaitable, Callable, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import ParamSpec, TypeVar, get_type_hints

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, create_model

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
        response_format: type[BaseModel],
    ) -> BaseModel:
        return await asyncio.to_thread(
            self._complete_sync, instructions, payload, results, response_format
        )

    def _complete_sync(
        self, instructions: str, payload: dict, results: ToolResults,
        response_format: type[BaseModel],
    ) -> BaseModel:
        try:
            from openai import AzureOpenAI, OpenAI
        except ModuleNotFoundError as error:
            if error.name != "openai":
                raise
            raise RuntimeError("Live mode requires: pip install openai") from error

        content = json.dumps({"request": payload, "trusted_tool_results": results})
        if self.provider == "foundry":
            try:
                from azure.ai.projects import AIProjectClient
                from azure.identity import DefaultAzureCredential
            except ModuleNotFoundError as error:
                if not error.name or not error.name.startswith("azure"):
                    raise
                raise RuntimeError(
                    "Foundry mode requires: pip install azure-ai-projects azure-identity openai"
                ) from error
            with (
                DefaultAzureCredential() as credential,
                AIProjectClient(
                    endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"], credential=credential,
                ) as project,
                project.get_openai_client() as client,
            ):
                response = client.responses.parse(
                    model=self.model, instructions=instructions,
                    input=content, text_format=response_format,
                )
                parsed = response.output_parsed
        else:
            if self.provider == "azure_openai":
                client = AzureOpenAI(
                    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                    api_key=os.environ["AZURE_OPENAI_API_KEY"],
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
                    timeout=45.0, max_retries=1,
                )
            elif self.provider == "github":
                client = OpenAI(
                    api_key=os.environ["GITHUB_TOKEN"],
                    base_url="https://models.github.ai/inference",
                    timeout=45.0, max_retries=1,
                )
            else:
                client = OpenAI(
                    api_key=os.environ["OPENAI_API_KEY"],
                    base_url=os.getenv("OPENAI_BASE_URL"),
                    timeout=45.0, max_retries=1,
                )
            with client:
                response = client.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": content},
                    ],
                    response_format=response_format,
                )
                parsed = response.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("The live model refused or omitted the structured response.")
        return response_format.model_validate(parsed)


def get_chat_client(model: str = MODEL_FAST_GREEN) -> ChatClient:
    """Resolve a model tier; simulation never imports or contacts a live SDK."""
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
            result = await asyncio.to_thread(self.tools[name], **arguments)
            if not isinstance(result, dict):
                raise TypeError(f"{name} must return a dictionary.")
            results.setdefault(name, []).append(result)
        if authoritative_tool is not None:
            if len(results.get(authoritative_tool, [])) != 1:
                raise ValueError("An authoritative action must return exactly one receipt.")
            value = results[authoritative_tool][0]
        elif self.client.mode == "simulation" or deterministic:
            value = self.simulator(payload, results)
        else:
            value = await self.client.complete(
                self.instructions, payload, results, self.response_format
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
