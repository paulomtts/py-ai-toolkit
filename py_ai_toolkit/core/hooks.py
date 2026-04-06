from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Type

from pydantic import BaseModel

from py_ai_toolkit.core.domain.schemas import CompletionResponse, EmbeddingUsage, ValidationConfig


@dataclass(frozen=True)
class BeforeRenderContext:
    template: str | None
    kwargs: dict[str, Any]


@dataclass(frozen=True)
class AfterRenderContext:
    prompt: str


@dataclass(frozen=True)
class BeforeLLMCallContext:
    messages: list[dict[str, str]]
    model: str
    response_model: Type | None


@dataclass(frozen=True)
class AfterLLMCallContext:
    response: CompletionResponse
    model: str
    elapsed_ms: float


@dataclass(frozen=True)
class AfterEmbedContext:
    embedding: list[float]
    model: str
    usage: EmbeddingUsage
    elapsed_ms: float


@dataclass(frozen=True)
class BeforeValidationContext:
    output: BaseModel
    config: ValidationConfig


@dataclass(frozen=True)
class AfterValidationContext:
    is_valid: bool
    failure_reasons: list[str]


@dataclass(frozen=True)
class OnRetryContext:
    current_retry: int
    max_retries: int
    evaluations: str


BeforeRenderHook = Callable[[BeforeRenderContext], Awaitable[None]]
AfterRenderHook = Callable[[AfterRenderContext], Awaitable[None]]
BeforeLLMCallHook = Callable[[BeforeLLMCallContext], Awaitable[None]]
AfterLLMCallHook = Callable[[AfterLLMCallContext], Awaitable[None]]
AfterEmbedHook = Callable[[AfterEmbedContext], Awaitable[None]]
BeforeValidationHook = Callable[[BeforeValidationContext], Awaitable[None]]
AfterValidationHook = Callable[[AfterValidationContext], Awaitable[None]]
OnRetryHook = Callable[[OnRetryContext], Awaitable[None]]


@dataclass
class Hooks:
    before_render: BeforeRenderHook | None = None
    after_render: AfterRenderHook | None = None
    before_llm_call: BeforeLLMCallHook | None = None
    after_llm_call: AfterLLMCallHook | None = None
    after_embed: AfterEmbedHook | None = None
    before_validation: BeforeValidationHook | None = None
    after_validation: AfterValidationHook | None = None
    on_retry: OnRetryHook | None = None


async def _fire_hook(hook: Callable | None, ctx: Any) -> None:
    if hook is not None:
        await hook(ctx)
