"""Introspection SDK instrumentation for LangGraph/LangChain runs."""

from __future__ import annotations

import os
from typing import Any

from langchain_core.runnables import RunnableConfig

_handler = None


def introspection_config(config: RunnableConfig | None, agent_name: str) -> RunnableConfig:
    config = config or {}

    if not os.environ.get("INTROSPECTION_TOKEN"):
        return config

    handler = _get_handler()
    callbacks = [handler, *[cb for cb in list(config.get("callbacks") or []) if cb is not handler]]
    configurable = dict(config.get("configurable") or {})
    metadata: dict[str, Any] = dict(config.get("metadata") or {})

    thread_id = configurable.get("thread_id") or configurable.get("conversation_id")
    if thread_id:
        metadata["gen_ai.conversation.id"] = str(thread_id)
        metadata["thread_id"] = str(thread_id)

    return {
        **config,
        "callbacks": callbacks,
        "configurable": configurable,
        "metadata": metadata,
        "run_name": agent_name,
    }


def _get_handler():
    global _handler

    if _handler is None:
        from introspection_sdk import IntrospectionCallbackHandler

        _handler = IntrospectionCallbackHandler(
            service_name="open-deep-research",
        )

    return _handler
