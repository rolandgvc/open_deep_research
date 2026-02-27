# I-4: Fix asyncio.gather to handle partial search failures gracefully

## Summary

**Context:** `tavily_search_async` in `utils.py` runs multiple search queries concurrently using `asyncio.gather`.

**Bug:** `asyncio.gather(*search_tasks)` without `return_exceptions=True` propagates the first exception and cancels all in-flight coroutines.

**Actual vs. expected:** A single rate-limit (429) or transient error on one query causes the entire batch to fail — even if other queries were about to return valid results. Expected: successful queries return their results; only failed queries are skipped.

**Impact:** Sections get written with zero source material when any single search query fails, undermining the system's core grounding and citation requirements.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L179" />

```python
search_docs = await asyncio.gather(*search_tasks)
# <-- BUG 🔴 No return_exceptions=True — one failure kills all queries
```

Additional instances of the same pattern:

- Line 819: `for response in await asyncio.gather(*search_tasks):`
- Line 1058: `updated_results = await asyncio.gather(*fetch_tasks)`
- Line 1084: `search_results = await asyncio.gather(*search_tasks)`

## Evidence

Tavily is the default search provider (`configuration.py` line 30: `search_api: SearchAPI = SearchAPI.TAVILY`). Every research step routes through these gather calls. When multiple sections are researched in parallel, concurrent batch searches are more likely to hit Tavily's per-minute rate limits, triggering 429 errors.

## Impact

- **Total data loss:** One 429 on any query in a batch → all queries in that batch cancelled → zero search results for the research step.
- **Hallucination cascade:** The section writer receives no source material and fills from training data with no citations — directly violating the grounding requirements.
- **Amplified by parallelism:** More sections researched in parallel = higher probability of hitting rate limits = more frequent total failures.

## Recommendation

### Suggested implementation

```python
# Replace all four instances of:
search_docs = await asyncio.gather(*search_tasks)

# With:
raw_results = await asyncio.gather(*search_tasks, return_exceptions=True)
search_docs = [r for r in raw_results if not isinstance(r, Exception)]
# Optionally log failed queries:
for i, r in enumerate(raw_results):
    if isinstance(r, Exception):
        logger.warning(f"Search query {i} failed: {r}")
```

Apply this pattern to all four `asyncio.gather` call sites in `utils.py` (L179, L819, L1058, L1084).

## Related

- I-3 (missing timeouts) — the timeout fix interacts with this; timed-out requests will produce exceptions that this fix would gracefully handle rather than crashing the batch.
