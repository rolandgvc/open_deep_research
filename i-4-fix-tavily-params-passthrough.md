# I-4: Tavily search parameters silently ignored despite config surface

## Summary

**Context:** `get_search_params()` filters Tavily-specific config keys (`max_results`, `topic`) from `search_api_config`. These are then passed to `select_and_execute_search()` as `params_to_pass`.

**Bug:** Two compounding issues prevent the params from taking effect:
1. `tavily_search()` hardcodes `max_results=5` and `topic="general"` in the tool body
2. `select_and_execute_search()` passes params as `ainvoke(**params_to_pass)` kwargs (runtime config), not as tool input fields

**Actual vs. expected:** Setting `search_api_config: {"max_results": 10, "topic": "news"}` has zero effect — Tavily always returns 5 general results.

**Impact:** Operators cannot tune search breadth or topic for Tavily despite the config surface suggesting they can.

## Where

Config accepts Tavily params:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L50-L56" />

```python
SEARCH_API_PARAMS = {
    "tavily": ["max_results", "topic"],  # Accepted but never used
    ...
}
```

Tool hardcodes values:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L1278-L1280" />

```python
search_results = await tavily_search_async(
    queries,
    max_results=5,       # <-- BUG 🔴 Hardcoded, ignores config
    topic="general",     # <-- BUG 🔴 Hardcoded, ignores config
    include_raw_content=True
)
```

Params passed incorrectly:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L1321" />

```python
return await tavily_search.ainvoke({'queries': query_list}, **params_to_pass)
# <-- BUG 🔴 params go to ainvoke runtime config, not tool input
```

## Evidence

### Trace through the code

1. Operator sets `SEARCH_API_CONFIG={"max_results": 10, "topic": "news"}` in env
2. `get_search_params("tavily", config)` returns `{"max_results": 10, "topic": "news"}`
3. `select_and_execute_search("tavily", queries, {"max_results": 10, "topic": "news"})` is called
4. `tavily_search.ainvoke({'queries': query_list}, max_results=10, topic="news")` — extra kwargs go to LangChain runnable config, not the tool function
5. Inside `tavily_search()`, `max_results=5` and `topic="general"` are hardcoded
6. Config has no effect

## Impact

- **Quality:** Cannot increase result count for deeper research on complex topics
- **Cost:** Cannot decrease result count for simple queries to reduce API spend
- **Trust:** Config appears to work (no errors) but silently does nothing

## Recommendation

Refactor `tavily_search` to accept `max_results` and `topic` as parameters with defaults:

```python
@tool
async def tavily_search(queries: List[str], max_results: int = 5, topic: str = "general") -> str:
    search_results = await tavily_search_async(
        queries,
        max_results=max_results,
        topic=topic,
        include_raw_content=True
    )
    ...
```

And update the dispatcher to pass params as tool input:

```python
if search_api == "tavily":
    tool_input = {'queries': query_list, **params_to_pass}
    return await tavily_search.ainvoke(tool_input)
```
