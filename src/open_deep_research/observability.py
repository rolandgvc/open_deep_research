import os
from contextlib import contextmanager
from functools import wraps
from inspect import iscoroutinefunction
from typing import Iterator, Optional

from introspection_sdk import IntrospectionSpanProcessor
from introspection_sdk.config import AdvancedOptions
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from openinference.instrumentation.langchain import LangChainInstrumentor

SERVICE_NAME = "open_deep_research"
_CONFIGURED = False


def configure_observability(*, force: bool = False, span_exporter=None) -> Optional[TracerProvider]:
    """Configure Introspection tracing for LangChain/LangGraph execution."""
    global _CONFIGURED

    if _CONFIGURED and not force:
        provider = trace.get_tracer_provider()
        return provider if isinstance(provider, TracerProvider) else None

    if span_exporter is None and not os.getenv("INTROSPECTION_TOKEN"):
        return None

    provider = TracerProvider(
        resource=Resource.create({"service.name": SERVICE_NAME})
    )
    processor_kwargs = {}
    if span_exporter is not None:
        processor_kwargs["advanced"] = AdvancedOptions(span_exporter=span_exporter)
    provider.add_span_processor(IntrospectionSpanProcessor(**processor_kwargs))
    trace.set_tracer_provider(provider)
    LangChainInstrumentor().instrument(tracer_provider=provider)
    _CONFIGURED = True
    return provider


def get_conversation_id(config) -> Optional[str]:
    """Extract the LangGraph thread ID for trace correlation."""
    configurable = config.get("configurable", {}) if config else {}
    thread_id = configurable.get("thread_id")
    return str(thread_id) if thread_id else None


@contextmanager
def trace_node(span_name: str, config=None, agent_name: Optional[str] = None) -> Iterator[None]:
    """Create a root span for a graph node when tracing is enabled."""
    provider = configure_observability()
    if provider is None:
        yield
        return

    tracer = trace.get_tracer(SERVICE_NAME)
    with tracer.start_as_current_span(span_name) as span:
        conversation_id = get_conversation_id(config)
        if conversation_id:
            span.set_attribute("gen_ai.conversation.id", conversation_id)
        if agent_name:
            span.set_attribute("gen_ai.agent.name", agent_name)
        yield


def traced_node(span_name: str, agent_name: Optional[str] = None):
    """Wrap a graph node in a root span when tracing is enabled."""

    def decorator(func):
        if iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(state, config, *args, **kwargs):
                with trace_node(span_name, config, agent_name=agent_name):
                    return await func(state, config, *args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(state, config, *args, **kwargs):
            with trace_node(span_name, config, agent_name=agent_name):
                return func(state, config, *args, **kwargs)

        return sync_wrapper

    return decorator
