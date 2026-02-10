# I-2: No error handling on LLM and HTTP calls in workflow graph nodes

## Summary

**Context:** The LangGraph workflow in `graph.py` orchestrates 6+ LLM calls per section across parallel sections, plus HTTP calls to search APIs (Perplexity, Google) via `utils.py`. A typical multi-section report involves 20-30+ external API calls over several minutes.

**Bug:** `graph.py` contains zero `try`/`except` blocks. Every LLM call (`structured_llm.ainvoke`, `writer_model.ainvoke`, `reflection_model.ainvoke`) and every downstream HTTP call is completely unprotected. Additionally, `compile_final_report` uses an unprotected dict lookup that throws `KeyError` if any section name mismatches.

**Actual vs. expected:** A single transient API failure (429 rate limit, 500 server error, timeout, malformed JSON from structured output) crashes the entire pipeline with an unhandled exception. Expected: retry transient failures, compile partial reports when possible.

**Impact:** Users lose all progress on multi-minute research jobs. Since sections run in parallel via `Send()`, one failed section crashes the entire batch. The `compile_final_report` KeyError at the very end can discard a fully-researched report.

## Where

### Unprotected LLM calls

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L86-L88" />

```python
structured_llm = planner_llm.with_structured_output(Sections)
report_sections = await structured_llm.ainvoke([...])
# <-- BUG 🔴 No try/except — structured output parse failure or API error crashes pipeline
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L294-L296" />

```python
section_content = await writer_model.ainvoke([...])
# <-- BUG 🔴 No try/except — failure here wastes all prior search work for this section
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L326-L327" />

```python
feedback = await reflection_model.ainvoke([...])
# <-- BUG 🔴 No try/except — grading failure after writing wastes all work
```

### Unprotected dict lookup in compile_final_report

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L420-L431" />

```python
completed_sections = {s.name: s.content for s in state["completed_sections"]}
for section in sections:
    section.content = completed_sections[section.name]
    # <-- BUG 🔴 KeyError if section name doesn't match — loses entire report
```

### HTTP calls without timeouts

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L232-L236" />

```python
response = requests.post("https://api.perplexity.ai/chat/completions", ...)
# <-- BUG 🔴 No timeout — can hang indefinitely on stalled connection
```

Note: The async paths (aiohttp, httpx) do have timeouts (10s and 30s respectively), but the synchronous `requests` calls do not.

## Evidence

### Scenario 1: Structured output parse failure

1. User starts a 5-section research report
2. Plan generation succeeds, human approves
3. 4 sections complete research and writing successfully
4. Section 5's grading call returns malformed JSON
5. `with_structured_output()` raises `OutputParserException`
6. Entire parallel batch crashes — all 5 sections lost

### Scenario 2: API rate limit during parallel sections

1. 5 sections kick off parallel research simultaneously
2. Each section generates 2 search queries → 10 concurrent API calls
3. Provider returns 429 on one call
4. Unhandled exception propagates up
5. All 5 sections' work is discarded

### Scenario 3: compile_final_report KeyError

1. Full report completes: 5 sections researched, written, graded
2. LLM subtly rephrases a section name during writing (e.g., "AI Ethics" → "AI Ethics & Governance")
3. `compile_final_report` looks up the original name
4. `KeyError` — user sees a crash instead of a report with all content already generated

## Impact

- **Reliability:** Every external API call is a potential crash point with no recovery
- **Cost:** Failed late-stage calls waste all prior API spend (search + LLM calls for prior sections)
- **User experience:** Multi-minute research jobs produce unhandled exceptions instead of partial results

## Recommendation

**Decision needed:** Whether failed sections produce placeholder text or trigger retry.

- Option A: Retry transient errors (429/500/503) with exponential backoff, then placeholder on persistent failure — simpler, preserves partial work
- Option B: Retry transient errors, then re-queue failed sections for a second attempt — better recovery but more complex state management

### Suggested implementation (Option A)

```python
# 1. Add retry helper
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

async def invoke_with_retry(model, messages, max_retries=3):
    """Invoke LLM with retry on transient failures."""
    for attempt in range(max_retries):
        try:
            return await model.ainvoke(messages)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            if is_transient(e):  # 429, 500, 503, timeout
                await asyncio.sleep(2 ** attempt)
            else:
                raise

# 2. Fix compile_final_report
completed_sections = {s.name: s.content for s in state["completed_sections"]}
for section in sections:
    section.content = completed_sections.get(section.name, section.content or "[Section not completed]")

# 3. Add timeouts to sync HTTP calls
response = requests.post(url, headers=headers, json=payload, timeout=30)
```

## Related

- Async HTTP calls in `utils.py` already have timeouts (aiohttp: 10s, httpx: 30s) — only sync `requests` calls are missing them
- `utils.py` has try/except blocks in search functions — the gap is specifically in `graph.py` node functions
