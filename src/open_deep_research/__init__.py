"""Planning, research, and report generation."""

import os

__version__ = "0.0.15"


def _setup_introspection() -> None:
    """Initialize Introspection SDK tracing for LangChain/LangGraph operations.

    Activates only when INTROSPECTION_TOKEN is set. Uses OpenInference
    LangChainInstrumentor to auto-capture all LangChain model calls,
    tool invocations, and LangGraph node transitions.
    """
    if not os.environ.get("INTROSPECTION_TOKEN"):
        return

    try:
        from introspection_sdk import IntrospectionSpanProcessor
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
    except ImportError:
        return

    provider = TracerProvider()
    provider.add_span_processor(
        IntrospectionSpanProcessor(service_name="open_deep_research")
    )
    trace.set_tracer_provider(provider)
    LangChainInstrumentor().instrument(tracer_provider=provider)


_setup_introspection()