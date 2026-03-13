from __future__ import annotations

import atexit
import inspect
import os
from contextlib import contextmanager
from functools import wraps
from threading import Lock
from typing import Any, Callable, Iterator, ParamSpec, TypeVar, cast

from introspection_sdk import IntrospectionSpanProcessor
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import baggage, context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

SERVICE_NAME = "open_deep_research"

P = ParamSpec("P")
R = TypeVar("R")

_lock = Lock()
_instrumented = False
_span_processor: IntrospectionSpanProcessor | None = None
_tracer_provider: TracerProvider | None = None


def configure_instrumentation() -> None:
    """Initialize Introspection tracing for LangChain operations."""
    global _instrumented, _span_processor, _tracer_provider

    if _instrumented or not os.getenv("INTROSPECTION_TOKEN"):
        return

    with _lock:
        if _instrumented:
            return

        _tracer_provider = TracerProvider(
            resource=Resource.create({"service.name": SERVICE_NAME})
        )
        _span_processor = IntrospectionSpanProcessor(system_name=SERVICE_NAME)
        _tracer_provider.add_span_processor(_span_processor)
        LangChainInstrumentor().instrument(tracer_provider=_tracer_provider)

        atexit.register(_span_processor.force_flush)
        _instrumented = True


@contextmanager
def _span_context(
    agent_name: str, config: dict[str, Any] | None = None
) -> Iterator[None]:
    """Attach agent and conversation context to traced operations."""
    configure_instrumentation()

    if _tracer_provider is None:
        yield
        return

    configurable = _get_configurable(config)
    conversation_id = configurable.get("thread_id") or configurable.get(
        "conversation_id"
    )
    user_id = configurable.get("user_id")

    current_context = baggage.set_baggage(
        "gen_ai.agent.name", agent_name, context.get_current()
    )
    if conversation_id:
        current_context = baggage.set_baggage(
            "gen_ai.conversation.id", str(conversation_id), current_context
        )
    if user_id:
        current_context = baggage.set_baggage(
            "identity.user.id", str(user_id), current_context
        )

    token = context.attach(current_context)
    tracer = _tracer_provider.get_tracer(SERVICE_NAME)
    try:
        with tracer.start_as_current_span(f"agent {agent_name}") as span:
            span.set_attribute("gen_ai.agent.name", agent_name)
            if conversation_id:
                span.set_attribute(
                    "gen_ai.conversation.id", str(conversation_id)
                )
            if user_id:
                span.set_attribute("identity.user.id", str(user_id))
            yield
    finally:
        context.detach(token)


def traced_agent(agent_name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Wrap a LangGraph node in an Introspection agent span."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                with _span_context(agent_name, _extract_config(args, kwargs)):
                    return await func(*args, **kwargs)

            return cast(Callable[P, R], async_wrapper)

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with _span_context(agent_name, _extract_config(args, kwargs)):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def _extract_config(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    """Extract RunnableConfig from a LangGraph node call."""
    if "config" in kwargs:
        return kwargs["config"]
    if len(args) > 1:
        return args[1]
    return None


def _get_configurable(config: Any) -> dict[str, Any]:
    """Normalize the configurable payload from RunnableConfig."""
    if not isinstance(config, dict):
        return {}

    configurable = config.get("configurable", {})
    if not isinstance(configurable, dict):
        return {}

    return configurable
