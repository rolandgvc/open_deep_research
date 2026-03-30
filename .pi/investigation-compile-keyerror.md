# Investigation: compile_final_report KeyError

**Issue:** compile_final_report crashes with KeyError when a research section fails to complete  
**File:** `src/open_deep_research/graph.py` lines 405–431

## Problem

`compile_final_report` builds a dict lookup and iterates all planned sections:

```python
completed_sections = {s.name: s.content for s in state["completed_sections"]}
for section in sections:
    section.content = completed_sections[section.name]   # unguarded KeyError
```

If any section subgraph exits with an unhandled exception before writing its `Section` output, that key is absent and the entire workflow crashes with `KeyError`, discarding all other completed sections.

## Mitigation already in place

The grading backstop (`max_search_depth`) ensures a section is always written after the grading loop exits — but only covers grade-fail retries. A transient network error, API timeout, or unhandled exception in `search_web` or `write_section` nodes can still prevent a section from appearing in `completed_sections`.

## Options

### Option A — Graceful fallback (minimal change)
```python
for section in sections:
    section.content = completed_sections.get(section.name, section.content or f"[Section '{section.name}' could not be completed]")
```
- Pro: 1-line fix, preserves partial report
- Con: User may not notice a section is missing unless the placeholder is visible

### Option B — Pre-compilation guard
Add a check before the loop:
```python
missing = [s.name for s in sections if s.name not in completed_sections]
if missing:
    raise ValueError(f"Missing completed sections: {missing}")
```
- Pro: Fail-fast with a clear error message
- Con: Still discards all completed work

### Option C — Retry missing sections
After detecting missing sections, re-dispatch failed section subgraphs before compiling.
- Pro: Best user outcome
- Con: Significant complexity; may be out of scope for this node

## Recommendation

**Option A** is the right first step — replace the bare dict lookup with `.get()` and a visible placeholder. This prevents the catastrophic crash-and-discard scenario. Pair it with a warning log so operators can detect incomplete reports in production.

## Decision needed

Which option to implement? Option A is low-risk and can be done now. Option C is a longer-term improvement.
