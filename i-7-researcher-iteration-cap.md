# I-7: Researcher agent loop has no iteration cap in multi-agent variant

## Summary

**Context:** The multi-agent variant uses `research_agent_should_continue` to decide whether a researcher keeps searching or stops. The workflow variant has `max_search_depth=2` as a config-driven guard.

**Bug:** `research_agent_should_continue` only checks `last_message.tool_calls` — it has no iteration count check. The `max_search_depth` config exists but is not wired into the multi-agent flow.

**Actual vs. expected:** Researchers loop until LangGraph's global recursion limit (default 25) instead of stopping after a bounded number of iterations.

**Impact:** Multiple parallel researchers can exhaust the global recursion budget unpredictably, causing `GraphRecursionError` with no partial output. Users lose all progress.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L281-L293" />

```python
async def research_agent_should_continue(state: SectionState) -> Literal["research_agent_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "research_agent_tools"  # <-- BUG 🔴 No iteration count check
    else:
        return END
```

The workflow variant enforces the limit:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/configuration.py#L27-L55" />

`max_search_depth` is defined in `Configuration` but never referenced in `multi_agent.py`.

## Evidence

1. Researcher starts, LLM decides to search → loop continues
2. LLM keeps issuing tool calls (common with broad topics)
3. No counter stops the loop — only LangGraph's global recursion limit (25 nodes total across all researchers)
4. With 5 parallel researchers, each can only average 5 iterations before hitting the global cap
5. First researcher to exhaust the budget causes `GraphRecursionError` for the entire graph

### Comparison with workflow variant

The workflow variant explicitly checks `search_iterations < max_search_depth` in `write_section`, proving the design intent exists but wasn't carried to multi-agent.

## Impact

- **Reliability:** Opaque `GraphRecursionError` with no partial output saved
- **Cost:** Unbounded Tavily API and LLM token spend per researcher
- **User experience:** Multi-minute research runs fail with no recovery

## Recommendation

Add iteration counting to `research_agent_should_continue` using the existing `max_search_depth` config:

```python
async def research_agent_should_continue(state: SectionState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    messages = state["messages"]
    last_message = messages[-1]
    # Count tool responses as proxy for iterations
    iterations = len([m for m in messages if hasattr(m, "type") and m.type == "tool"])
    if last_message.tool_calls and iterations < configurable.max_search_depth:
        return "research_agent_tools"
    return END
```

This reuses the existing config field, keeping behavior consistent with the workflow variant.

## Related

- I-8: No retry logic on API calls (compounding — a failed search in an unbounded loop wastes even more resources)
