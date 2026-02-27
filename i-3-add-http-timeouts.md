# I-3: Add timeouts to external HTTP calls (Perplexity API, Google scraping)

## Summary

**Context:** `utils.py` makes HTTP requests to the Perplexity API and Google search scraping endpoint as part of the research workflow.

**Bug:** Both `requests.post` (Perplexity, L232) and `requests.get` (Google, L938) have no `timeout` parameter.

**Actual vs. expected:** A stalled upstream blocks the entire process indefinitely. Expected: requests time out after a reasonable period and raise an exception that can be handled.

**Impact:** A single hung HTTP request freezes the entire report generation run with no recovery. The Perplexity call is additionally synchronous inside an async workflow, blocking the event loop.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L232-L236" />

```python
response = requests.post(
    "https://api.perplexity.ai/chat/completions",
    headers=headers,
    json=payload
)
# <-- BUG 🔴 No timeout parameter — blocks indefinitely on upstream hang
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L938-L955" />

```python
resp = requests.get(
    # Google search URL
)
# <-- BUG 🔴 No timeout parameter
```

## Evidence

Both calls use the `requests` library which defaults to no timeout (waits forever). The Perplexity call is synchronous but called from an async context (`select_and_execute_search`), meaning it blocks the event loop thread during execution.

## Impact

- **Availability:** Any Perplexity or Google upstream slowdown (network partition, API degradation, DNS resolution hang) blocks the entire research run indefinitely.
- **Concurrency:** The synchronous Perplexity call on the async event loop blocks other concurrent operations during busy research runs.
- **No user feedback:** No timeout means no error to catch — the run just hangs silently.

## Recommendation

### Suggested implementation

```python
# Perplexity — add timeout and consider async
response = requests.post(
    "https://api.perplexity.ai/chat/completions",
    headers=headers,
    json=payload,
    timeout=30  # 30s is generous for an API call
)

# Google scraping — add timeout
resp = requests.get(url, timeout=15)
```

**Additionally:** Consider wrapping the synchronous Perplexity call in `asyncio.get_event_loop().run_in_executor(None, ...)` to avoid blocking the event loop, or migrate to `httpx.AsyncClient` for native async HTTP.

**Optional enhancement:** Add retry with exponential backoff for transient 429/503 errors on both endpoints.
