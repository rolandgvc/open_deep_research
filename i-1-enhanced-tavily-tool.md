# I-1: Supervisor/research prompts call unregistered enhanced_tavily_search tool

## Summary

**Context:** The multi-agent supervisor and researcher prompts direct the model to use a web search tool while the graph registers the actual tool implementation.

**Bug:** The prompts instruct the model to call `enhanced_tavily_search`, but the multi-agent tool registry only exposes `tavily_search` and `duckduckgo_search`.

**Actual vs. expected:** The model produces tool calls for an unregistered tool name instead of the registered search tools.

**Impact:** Tool calls fail or are skipped, leaving the supervisor/researcher without search context and producing incomplete reports.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L258-L395" />
<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L17-L35" />

```python
# prompts.py
"""
Use enhanced_tavily_search to gather sources.
"""
# <-- BUG 🔴 Prompt references a tool that is not registered
```

```python
# multi_agent.py
if search_api == SearchAPI.TAVILY:
    return tavily_search
elif search_api == SearchAPI.DUCKDUCKGO:
    return duckduckgo_search
# <-- BUG 🔴 No enhanced_tavily_search alias registered
```

## Evidence

### Example

1. Supervisor prompt instructs the model to call `enhanced_tavily_search`.
2. The model emits a tool call with name `enhanced_tavily_search`.
3. The tool registry only exposes `tavily_search` and `duckduckgo_search`, so the call is unbound.

### Inconsistency

- Prompt guidance: `enhanced_tavily_search`
- Tool registry: `tavily_search`, `duckduckgo_search`

## Impact

- **Reliability:** Tool-call errors or skipped searches when the model follows the prompt.
- **Output quality:** Reports can be generated without web sources, leading to empty or incomplete sections.

## Recommendation

Align the prompts with the registered tool names or register an alias for backward compatibility.

**Decision needed:**

- Option A: Update prompts to reference `tavily_search`/`duckduckgo_search` (simplest, but breaks expectations if other code assumes the old name).
- Option B: Register an `enhanced_tavily_search` wrapper that forwards to `tavily_search` (keeps prompt wording stable).

### Suggested implementation (Option B)

```python
# Example: add alias when constructing tools
search_tool = get_search_tool(config.search_api)
search_tools = {
    "tavily_search": search_tool,
    "enhanced_tavily_search": search_tool,
}
```

## Related

None.
