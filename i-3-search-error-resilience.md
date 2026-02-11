# I-3: Search functions crash on transient failures and can hang indefinitely

## Summary

**Context:** The workflow executes 2+ search queries per section in parallel using `asyncio.gather()`, across multiple search provider implementations.

**Bug:** Two related resilience gaps: (1) `asyncio.gather()` is used without `return_exceptions=True` in three search functions, so a single query failure crashes the entire step. (2) `perplexity_search` uses synchronous `requests.post()` without a timeout, blocking the async event loop.

**Actual vs. expected:** A single transient API error should be logged and skipped while preserving results from other queries. Instead, it crashes the entire search step and discards all successful results. Perplexity requests should have a timeout; instead they can hang indefinitely.

**Impact:** Transient 429/500/timeout errors from any search API crash the entire workflow step. Perplexity API slowness hangs the whole workflow with no recovery.

## Where

### Problem 1: asyncio.gather without error handling

`tavily_search_async` — line 179:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L166-L180" />

```python
search_docs = await asyncio.gather(*search_tasks)
# <-- BUG 🔴 No return_exceptions=True — one failure kills all results
```

`linkup_search` — line 819:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L818-L829" />

`google_search_async` — line 1084:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L1079-L1086" />

### Problem 2: Perplexity synchronous blocking with no timeout

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L216-L236" />

```python
response = requests.post(
    "https://api.perplexity.ai/chat/completions",
    headers=headers,
    json=payload
)
# <-- BUG 🔴 No timeout parameter. Synchronous call blocks the async event loop.
```

Called from async context without run_in_executor:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L1327-L1329" />

## Evidence

- `rg "return_exceptions" src/open_deep_research/utils.py` returns no results — none of the 4 asyncio.gather calls use error handling
- `perplexity_search` uses `requests.post()` (synchronous) with no `timeout` parameter
- `perplexity_search` is called directly from the async `select_and_execute_search` function without `run_in_executor`
- With 2+ queries per search step and 5-8 sections per report, each report makes 10-16+ search API calls — significant probability of at least one transient failure

## Impact

- **Workflow crashes:** A single 429 rate limit, 500 server error, or DNS timeout from any search query crashes the entire step, discarding all successful results from parallel queries
- **Indefinite hangs:** When Perplexity is the configured search provider, a slow or unresponsive API hangs the entire workflow with no timeout or cancellation
- **Lost progress:** Without checkpointing (separate issue), a search crash forces restarting the entire multi-minute pipeline from scratch

## Recommendation

### Fix 1: asyncio.gather error handling

```python
# In tavily_search_async, linkup_search, google_search_async:
import logging
logger = logging.getLogger(__name__)

results = await asyncio.gather(*search_tasks, return_exceptions=True)
search_docs = []
for i, result in enumerate(results):
    if isinstance(result, Exception):
        logger.warning(f"Search query {i} failed: {result}")
    else:
        search_docs.append(result)
```

### Fix 2: Perplexity timeout and async

```python
# Option A: Add timeout (minimal change)
response = requests.post(url, headers=headers, json=payload, timeout=30)

# Option B: Convert to async (recommended for consistency)
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.post(url, headers=headers, json=payload)
```

Both fixes are independent and can be applied separately.
