"""Introspection SDK tracing configuration."""

from __future__ import annotations

import atexit
import os

from introspection_sdk import IntrospectionClient, IntrospectionSpanProcessor
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

_SERVICE_NAME = os.getenv("INTROSPECTION_SERVICE_NAME", "open_deep_research")
_configured = False
_processor: IntrospectionSpanProcessor | None = None
_client = IntrospectionClient(service_name=_SERVICE_NAME)


def configure_tracing() -> IntrospectionClient:
    """Configure OpenTelemetry + Introspection tracing once per process."""
    global _configured, _processor

    if _configured:
        return _client

    if not os.getenv("INTROSPECTION_TOKEN"):
        _configured = True
        return _client

    provider = TracerProvider(
        resource=Resource.create({"service.name": _SERVICE_NAME})
    )
    _processor = IntrospectionSpanProcessor()
    provider.add_span_processor(_processor)
    trace.set_tracer_provider(provider)

    LangChainInstrumentor().instrument(tracer_provider=provider)

    def _shutdown() -> None:
        if _processor is None:
            return
        _processor.force_flush()
        _processor.shutdown()

    atexit.register(_shutdown)
    _configured = True
    return _client


__all__ = ["configure_tracing"]


