# I-4: No retry or error handling on LLM and Tavily search API calls

## Summary

**Context:** A deep-research run makes 15-30+ LLM API calls and multiple search API calls over several minutes.

**Bug:** All LLM calls in `graph.py` are bare `await model.ainvoke(...)` with no try/except, retry, or timeout. Tavily search (the default search backend) uses bare `asyncio.gather()` with no exception handling. By contrast, DuckDuckGo search already implements 3-retry exponential backoff.

**Actual vs. expected:** Any transient 429/500 error terminates the entire workflow with a raw traceback. Expected: transient errors are retried automatically.

**Impact:** Users lose all research progress (multi-minute run) on any transient API failure. No way to resume.

## Where

### LLM calls (graph.py)

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L282-L285" />

```python
# Bare ainvoke — no retry, no try/except
section_content = await writer_model.ainvoke([
    SystemMessage(content=section_writer_instructions),
    HumanMessage(content=section_writer_inputs_formatted)
])
# <-- BUG 🔴 Same pattern in all 5+ graph nodes
```

### Tavily search (utils.py)

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L152-L167" />

```python
# Bare asyncio.gather — any single failure crashes the run
search_docs = await asyncio.gather(*search_tasks)
# <-- BUG 🔴 No return_exceptions=True, no retry
```

## Evidence

### Inconsistency

DuckDuckGo search (alternate backend) has robust retry:
- `max_retries=3`, exponential backoff, graceful degradation

Tavily search (default backend, most-used path) has none — the most likely failure path is the least protected.

### Affected nodes

1. `generate_report_plan` — 2 LLM calls
2. `generate_queries` — 1 LLM call per section (parallel)
3. `write_section` — 2 LLM calls per section (writer + grader)
4. `write_final_sections` — 1 LLM call per non-research section
5. Each of these also triggers Tavily search calls

## Recommendation

**Decision needed:**

- Option A: Use LangChain's built-in `model.with_retry()` for LLM calls + apply DuckDuckGo's retry pattern to Tavily
- Option B: Wrap all external calls with `tenacity` (3 retries, exponential backoff starting at 1s)

### Suggested implementation (Option A — minimal)

```python
# For LLM calls — add .with_retry() when initializing models:
writer_model = init_chat_model(...).with_retry(
    stop_after_attempt=3,
    wait_exponential_jitter=True
)

# For Tavily search — add return_exceptions=True and filter:
search_docs = await asyncio.gather(*search_tasks, return_exceptions=True)
search_docs = [doc for doc in search_docs if not isinstance(doc, Exception)]
```

Both approaches are compatible with LangGraph's checkpointing (retrying within a node is safe).
