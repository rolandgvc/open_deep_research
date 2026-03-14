# I-2: Multi-agent path crashes at runtime for 6 of 8 configured search providers

## Summary

**Context:** Both the workflow and multi-agent graphs share a `Configuration` dataclass with a `search_api` field that accepts 8 `SearchAPI` enum values.

**Bug:** The multi-agent graph's `get_search_tool()` only handles `tavily` and `duckduckgo`, raising `NotImplementedError` for the other 6 valid providers.

**Actual vs. expected:** Selecting `perplexity`, `exa`, `arxiv`, `pubmed`, `linkup`, or `googlesearch` crashes the multi-agent graph immediately. Expected: either work or reject at config time.

**Impact:** Users who configure a non-Tavily/DuckDuckGo provider and use the multi-agent graph get an unrecoverable crash before any report generation begins.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L17-L35" />

```python
def get_search_tool(config: RunnableConfig):
    """Get the appropriate search tool based on configuration"""
    configurable = Configuration.from_runnable_config(config)
    search_api = get_config_value(configurable.search_api)

    if search_api.lower() == "tavily":
        return tavily_search
    elif search_api.lower() == "duckduckgo":
        return duckduckgo_search
    else:
        # <-- BUG 🔴 Crashes for 6 valid SearchAPI values
        raise NotImplementedError(...)
```

The workflow path supports all 8 providers via `select_and_execute_search()`:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L1307-L1338" />

## Evidence

### Inconsistency

The `SearchAPI` enum in `configuration.py` defines 8 values, all documented in the README. The workflow graph handles all 8 via `select_and_execute_search()`. The multi-agent graph only handles 2.

| Provider     | Workflow graph | Multi-agent graph |
| ------------ | -------------- | ----------------- |
| tavily       | ✓              | ✓                 |
| duckduckgo   | ✓              | ✓                 |
| perplexity   | ✓              | ✗ crash           |
| exa          | ✓              | ✗ crash           |
| arxiv        | ✓              | ✗ crash           |
| pubmed       | ✓              | ✗ crash           |
| linkup       | ✓              | ✗ crash           |
| googlesearch | ✓              | ✗ crash           |

### Example

1. Set `search_api: "perplexity"` in config
2. Start the multi-agent graph
3. Graph crashes immediately with `NotImplementedError` before any research begins

## Impact

- **User experience:** Immediate crash with no report output for valid configuration
- **Discoverability:** Error message tells user to switch to "graph-based implementation" but doesn't explain how

## Recommendation

**Decision needed:**

- Option A: **Reuse `select_and_execute_search()`** — Wrap the existing workflow search dispatcher as a LangChain tool for the multi-agent path. This is the lowest-effort option and keeps search behavior consistent across both graphs.
- Option B: **Validate at config time** — Add a `supported_search_apis` set per graph variant and reject unsupported values during `Configuration.from_runnable_config()`. This is simpler but reduces multi-agent functionality.
- Option C: **Both** — Add validation now, implement full support later.

### Suggested implementation (Option A)

```python
# In multi_agent.py
from open_deep_research.utils import select_and_execute_search, get_search_params

async def generic_search(query: str, config: RunnableConfig) -> str:
    """Search tool that routes through all supported providers."""
    configurable = Configuration.from_runnable_config(config)
    search_api = get_config_value(configurable.search_api)
    search_api_config = configurable.search_api_config or {}
    params = get_search_params(search_api, search_api_config)
    return await select_and_execute_search(search_api, [query], params)

# Replace get_search_tool() with generic_search wrapped as a tool
```

## Related

- Existing PR for Tavily params passthrough: `introspection/i-4-fix-tavily-params-passthrough`
