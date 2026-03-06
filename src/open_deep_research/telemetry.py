from __future__ import annotations

import asyncio
import functools
import os
from contextlib import asynccontextmanager, contextmanager
from typing import Callable, ParamSpec, TypeVar

from introspection_sdk import IntrospectionSpanProcessor
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

_SERVICE_NAME = "open_deep_research"
_INITIALIZED = False

P = ParamSpec("P")
R = TypeVar("R")


def initialize_tracing() -> None:
    """Initialize OpenTelemetry tracing with the Introspection exporter."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    if not os.getenv("INTROSPECTION_TOKEN"):
        return

    provider = TracerProvider(
        resource=Resource.create({"service.name": _SERVICE_NAME})
    )
    provider.add_span_processor(IntrospectionSpanProcessor())
    trace.set_tracer_provider(provider)
    LangChainInstrumentor().instrument(tracer_provider=provider)
    _INITIALIZED = True


@contextmanager
def workflow_span(name: str):
    with trace.get_tracer("open_deep_research.workflow").start_as_current_span(
        name
    ):
        yield


@asynccontextmanager
async def workflow_span_async(name: str):
    with trace.get_tracer("open_deep_research.workflow").start_as_current_span(
        name
    ):
        yield


def workflow_step(name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorate a workflow step with an OpenTelemetry span."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                async with workflow_span_async(name):
                    return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with workflow_span(name):
                return func(*args, **kwargs)

        return wrapper

    return decorator
