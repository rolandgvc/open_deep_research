# I-2: Add error handling to workflow graph nodes

## Summary

**Context:** The Deep Research Reports workflow (`graph.py`) orchestrates 6+ graph nodes that make 20-30+ external API calls (LLM + search) over several minutes to produce a multi-section report.

**Bug:** Zero `try`/`except` blocks exist across all graph node functions. Any transient failure (rate limit, timeout, network error, malformed response) crashes the entire pipeline. Additionally, `compile_final_report` uses a strict dict lookup (`completed_sections[section.name]`) that raises `KeyError` if any section is missing.

**Impact:** A single 429 rate limit error or network timeout during section writing (after minutes of completed research) crashes the workflow and loses all progress. The compilation step compounds this — if any section fails to produce output, it discards all successfully completed sections.

## Where

### Unprotected LLM calls in graph nodes

All node functions call external services without error handling:

```python
# graph.py L86-93 — generate_report_plan
structured_llm = planner_llm.with_structured_output(Sections)
report_sections = await structured_llm.ainvoke(...)
# No try/except — any LLM error crashes the workflow
```

Same pattern repeats in:
- `generate_queries` (L218) — LLM call for search queries
- `search_web` (L252) — search API calls
- `write_section` (L295-296, L326-327) — LLM calls for section drafting and grading
- `write_final_sections` (L375-376) — LLM calls for intro/conclusion

### Unsafe dict lookup in compile_final_report

```python
# graph.py L420-431
def compile_final_report(state: ReportState):
    sections = state["sections"]
    completed_sections = {s.name: s.content for s in state["completed_sections"]}
    for section in sections:
        section.content = completed_sections[section.name]
        # <-- BUG 🔴 KeyError if any section is missing from completed_sections
```

### Contrast with utils.py

The search utility functions in `utils.py` DO have error handling (e.g., `exa_search` catches per-query exceptions and returns placeholder results), but the graph nodes calling them don't handle errors from the LLM calls that follow.

## Evidence

- `rg "try:|except" graph.py` returns zero matches
- `utils.py` search functions have try/except (exa_search, arxiv_search_async, etc.)
- Graph nodes are completely unprotected
- `compile_final_report` line 426 uses bare dict access without `.get()` fallback

## Impact

- **Cost waste:** 20-30+ paid API calls per report. A failure at section 4/5 wastes all prior work.
- **User experience:** Multi-minute workflow fails with raw exception, no partial results returned.
- **Compilation cascade:** Even if error handling were added to nodes, the `compile_final_report` function would still crash if any section is absent.

## Recommendation

### Option A: Node-level error handling (minimal)

Add try/except to each node function, catching transient errors and returning graceful fallbacks:

```python
async def write_section(state: SectionState, config: RunnableConfig):
    try:
        # ... existing LLM call logic ...
        result = await writer_llm.ainvoke(...)
    except Exception as e:
        logger.error(f"Section '{state['section'].name}' failed: {e}")
        # Return a failure marker instead of crashing
        return {"completed_sections": [state["section"].name + " [FAILED]"]}
```

### Option B: Node-level + compilation resilience (recommended)

Add error handling to nodes AND make `compile_final_report` defensive:

```python
def compile_final_report(state: ReportState):
    sections = state["sections"]
    completed_sections = {s.name: s.content for s in state["completed_sections"]}
    
    missing = [s.name for s in sections if s.name not in completed_sections]
    if missing:
        logger.warning(f"Missing sections: {missing}")
    
    for section in sections:
        section.content = completed_sections.get(
            section.name, 
            f"[Section '{section.name}' could not be completed]"
        )
    
    all_sections = "\n\n".join([s.content for s in sections])
    return {"final_report": all_sections}
```

**Decision needed:** Whether failed sections should produce placeholder text in the final report (partial output) or trigger a user-facing retry prompt.
