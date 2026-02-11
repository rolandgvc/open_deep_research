# I-5: compile_final_report crashes with KeyError when any section fails upstream

## Summary

**Context:** `compile_final_report` assembles all researched sections into the final report by looking up each planned section's content from `completed_sections`.

**Bug:** The lookup uses a raw dict access (`completed_sections[section.name]`) with no error handling. If any section fails to complete upstream, it won't be in the dict and the lookup crashes with `KeyError`.

**Actual vs. expected:** A single section failure crashes the entire report compilation. Expected: partial report with available sections, or a clear error listing which sections are missing.

**Impact:** All successfully completed sections are lost. Combined with issue #3 (search crash on transient failures), any transient API error propagates into total report loss.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L405-L431" />

```python
completed_sections = {s.name: s.content for s in state["completed_sections"]}
for section in sections:
    section.content = completed_sections[section.name]  # <-- BUG 🔴 KeyError if section missing
```

## Evidence

### Example

User runs a 5-section report. Section 3's search API returns a transient 500 error.

1. Sections 1, 2, 4, 5 complete successfully and are added to `completed_sections`
2. Section 3 fails during search and never completes
3. `compile_final_report` iterates over all 5 planned sections
4. Crashes with `KeyError` on section 3's name
5. Sections 1, 2, 4, 5 — all successfully researched — are lost

## Impact

- **Reliability:** Single section failure causes total report loss
- **User experience:** Users see a crash instead of a partial report after minutes of processing
- **Amplification:** Existing search crash issue (#3) now propagates to full pipeline failure

## Recommendation

Add defensive handling for missing sections.

**Decision needed:**

- Option A: Use `.get()` with placeholder — `completed_sections.get(section.name, "[Section not completed due to upstream error]")`. Produces a partial report with clear markers for failed sections.
- Option B: Pre-validate all sections exist before compilation. If any are missing, surface a clear error listing which sections failed, and optionally compile the available ones.

### Suggested implementation (Option A)

```python
completed_sections = {s.name: s.content for s in state["completed_sections"]}
for section in sections:
    if section.name in completed_sections:
        section.content = completed_sections[section.name]
    else:
        section.content = f"[Section '{section.name}' could not be completed due to an upstream error]"

# Compile final report from available sections
all_sections = "\n\n".join([s.content for s in sections])
return {"final_report": all_sections}
```

## Related

- Issue #3: Search functions crash on transient failures (upstream cause)
- Issue #4: No checkpointing (no way to retry from mid-point)
