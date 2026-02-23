# I-8: No retry logic or timeouts on LLM and search API calls

## Summary

**Context:** Open Deep Research makes multiple LLM API calls (plan, query generation, section writing) and search API calls (Tavily, Perplexity, DuckDuckGo, Exa) during a single research run that can take several minutes.

**Bug:** All LLM calls use bare `ainvoke()` with no retry, timeout, or error handling. Perplexity search uses `requests.post()` without a timeout. Tavily async search uses `asyncio.gather` without per-task retry. Only DuckDuckGo search has exponential backoff.

**Actual vs. expected:** A single transient API error (429, 503) terminates the entire run instead of retrying.

**Impact:** Users lose multi-minute research runs to transient errors with no recovery, no partial output, and no actionable error message.

## Where

### LLM call sites (no retry anywhere)

**multi_agent.py — supervisor node:**
<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L88-L107" />

**graph.py — all node functions** (`generate_report_plan`, `generate_queries`, `write_section`, `write_final_sections`) use bare `ainvoke()`.

### Search call sites

**utils.py — perplexity_search (~line 232):**
```python
response = requests.post(url, json=payload, headers=headers)
# <-- BUG 🔴 No timeout parameter — blocks indefinitely if API hangs
```

**utils.py — tavily_search_async:**
```python
search_tasks = [tavily_client.search(query, ...) for query in queries]
results = await asyncio.gather(*search_tasks)
# <-- BUG 🔴 No retry on individual tasks
```

**utils.py — duckduckgo_search (~line 1183):** ✅ Has exponential backoff (good)

## Evidence

1. All `ainvoke()` calls are bare — no try/except, no retry decorator
2. `perplexity_search` has no `timeout=` parameter on `requests.post()`
3. `tavily_search_async` wraps tasks in `asyncio.gather` with no error handling
4. `duckduckgo_search` is the only search function with proper retry logic, proving the pattern is known but inconsistently applied
5. Research runs involve 5-15+ API calls (plan + queries + sections), so exposure to at least one transient error is high for any run

## Impact

- **Reliability:** Any single transient error kills the entire run
- **User experience:** No partial output, no actionable error, must restart from scratch
- **Availability:** Perplexity calls can block indefinitely, hanging the entire workflow

## Recommendation

### 1. Shared retry helper for LLM calls

```python
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

@retry(
    retry=retry_if_exception_type((RateLimitError, APIStatusError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(4)
)
async def invoke_with_retry(llm, messages, **kwargs):
    return await llm.ainvoke(messages, **kwargs)
```

Replace all `llm.ainvoke(...)` calls with `invoke_with_retry(llm, ...)`.

### 2. Timeout on Perplexity search

```python
response = requests.post(url, json=payload, headers=headers, timeout=30)
```

### 3. Per-task retry on Tavily async

Wrap each task in a retry-enabled helper before passing to `asyncio.gather`.

### Implementation notes

- Use `tenacity` (already available via LangChain dependencies) for consistent retry patterns
- Catch provider-specific error types (OpenAI `RateLimitError`, Anthropic `RateLimitError`) rather than bare `Exception`
- DuckDuckGo already has the right pattern — align the other search functions with it

## Related

- I-7: Unbounded researcher loops compound this — an unbounded loop with no retry wastes even more resources before failing
