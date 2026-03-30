"""Planning, research, and report generation."""

__version__ = "0.0.15"


def _setup_introspection() -> None:
    """Initialize Introspection SDK tracing when INTROSPECTION_TOKEN is set.

    Uses OpenInference LangChain auto-instrumentation so every LLM, tool,
    and chain call in both graph implementations is traced automatically.
    """
    import os

    if not os.environ.get("INTROSPECTION_TOKEN"):
        return

    try:
        from introspection_sdk import IntrospectionSpanProcessor
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        provider.add_span_processor(
            IntrospectionSpanProcessor(service_name="open_deep_research")
        )
        trace.set_tracer_provider(provider)

        LangChainInstrumentor().instrument(tracer_provider=provider)
    except ImportError:
        pass


_setup_introspection()