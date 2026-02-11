"""Introspection SDK tracing configuration."""

from __future__ import annotations

import atexit
import os

from introspection_sdk import IntrospectionSpanProcessor
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

_SERVICE_NAME = os.getenv("INTROSPECTION_SERVICE_NAME", "open_deep_research")
_configured = False
_processor: IntrospectionSpanProcessor | None = None


def configure_tracing() -> None:
    """Configure OpenTelemetry + Introspection tracing once per process."""
    global _configured, _processor

    if _configured:
        return

    provider = TracerProvider()
    _processor = IntrospectionSpanProcessor(service_name=_SERVICE_NAME)
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


__all__ = ["configure_tracing"]


