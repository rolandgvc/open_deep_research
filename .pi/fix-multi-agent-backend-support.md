# Multi-agent graph crashes for 6 of 8 configured search backends

## Summary

**Context:** Both the workflow graph (`graph.py`) and the multi-agent graph (`multi_agent.py`) share a single `Configuration` dataclass that exposes all eight search backends via the `SearchAPI` enum.

**Bug:** `get_search_tool()` in `multi_agent.py` only handles `"tavily"` and `"duckduckgo"`. All other values raise `NotImplementedError` with a TODO comment. The workflow graph (`graph.py`) supports all eight backends cleanly via `select_and_execute_query`.

**Actual vs. expected:** A user who sets `search_api=exa` and invokes the multi-agent graph receives a `NotImplementedError` mid-run — after the supervisor has already initialized and possibly completed a clarification exchange. Expected: startup-time validation or full backend parity.

**Impact:** Six of the eight advertised backends are unusable in the multi-agent graph. Errors surface mid-run with no partial output and no graceful degradation.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L24-L38" />

```python
def get_search_tool(config: RunnableConfig) -> BaseTool:
    configurable = Configuration.from_runnable_config(config)
    if configurable.search_api == SearchAPI.TAVILY:
        return tavily_search
    elif configurable.search_api == SearchAPI.DUCKDUCKGO:
        return duckduckgo_search
    else:
        raise NotImplementedError(  # <-- BUG: 6 of 8 backends crash here
            f"Search API {configurable.search_api} not supported as a tool. "
            "Please use the graph-based implementation in `src/open_deep_research/graph.py` "
            "for other search APIs, or set `search_api` to 'tavily'."
        )
```

## Evidence

### Example

1. User configures `search_api=exa` in LangGraph config and invokes the `open_deep_research_multi_agent` graph.
2. Supervisor initializes, may complete one clarification exchange.
3. Supervisor attempts to call the search tool → `get_search_tool()` raises `NotImplementedError`.
4. Run terminates with an unhandled exception; no partial output is returned.

### Inconsistency

`utils.py` defines working implementations for all eight backends (`exa_search`, `arxiv_search`, `pubmed_search`, `perplexity_search`, etc.). `graph.py` routes to them cleanly via `select_and_execute_query`. `multi_agent.py` does not use any of these — only two `@tool`-wrapped versions exist (`tavily_search`, `duckduckgo_search`).

The shared `Configuration` schema makes no distinction between the two graphs, so the contract is broken silently.

## Impact

- **Functional:** Six of eight advertised search backends are unusable in the multi-agent graph.
- **User experience:** Errors surface mid-run after partial work has already executed.
- **Trust:** The shared Configuration schema implies parity between graph implementations; the gap is invisible at configuration time.

## Recommendation

**Decision needed:**

- **Option A — Startup validation:** Add a validator in `Configuration.from_runnable_config` (or in the multi-agent graph entry node) that checks `search_api` against the supported set `{tavily, duckduckgo}` and raises a descriptive `ValueError` immediately at graph construction time. Fast to implement; does not add backend parity.
- **Option B — Full backend parity:** Wrap the remaining six search functions from `utils.py` as `@tool` functions (following the `tavily_search` pattern) and route them through `get_search_tool()`. Higher effort; closes the functional gap entirely and aligns both graph implementations.
- **Option C — Schema split:** Define a narrower `MultiAgentSearchAPI` enum with only the two supported backends and use it in the multi-agent graph's configuration path. Prevents the contract mismatch at the type level.

### Suggested implementation (Option A — fastest fix)

```python
# In multi_agent.py, get_search_tool() or in graph entry node:
SUPPORTED_MULTI_AGENT_BACKENDS = {SearchAPI.TAVILY, SearchAPI.DUCKDUCKGO}

def get_search_tool(config: RunnableConfig) -> BaseTool:
    configurable = Configuration.from_runnable_config(config)
    if configurable.search_api not in SUPPORTED_MULTI_AGENT_BACKENDS:
        raise ValueError(
            f"search_api='{configurable.search_api}' is not supported by the multi-agent graph. "
            f"Supported backends: {[s.value for s in SUPPORTED_MULTI_AGENT_BACKENDS]}. "
            "Use the workflow graph for other backends."
        )
    if configurable.search_api == SearchAPI.TAVILY:
        return tavily_search
    return duckduckgo_search
```

## Related

- Duplicate `search_api` field in `configuration.py` (lines ~26 and ~36) — Python silently takes the second definition. Minor code smell, low runtime impact.
- `utils.py` contains working implementations of all 8 backends that Option B could wrap.
