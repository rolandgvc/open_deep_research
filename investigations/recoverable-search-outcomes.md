# Empty search results can be treated as report evidence

## Summary

**Context:** Open Deep Research depends on web search results for planning and writing report sections.

**Problem:** Search utilities return formatted strings directly to planning and writing prompts. Some no-result paths return natural-language messages, while other provider failures can raise exceptions, so the graph cannot reliably tell valid evidence apart from empty or failed search.

**Impact:** A writer can draft a section from an error message instead of source material, or a run can stop abruptly without a recovery path for the user.

**Recommendation:** Normalize search execution into explicit outcomes and gate downstream writing on valid source material.

## Evidence

- Linked issue: https://introspection.dev/issues/019e3a40-79da-775d-b88d-125ff9928c28
- `src/open_deep_research/utils.py` returns a plain no-results message from DuckDuckGo when no valid URLs are found.
- `select_and_execute_search` returns provider output as a string to the planner or section writer.
- The workflow inserts that returned value into planning context or `<Source material>` with no shared success, empty, or error envelope.

## Options

| Option | What changes | Pros | Cons |
| ------ | ------------ | ---- | ---- |
| A | Introduce a `SearchOutcome` shape with `status`, `sources`, `formatted_text`, and `error` fields. | Clear downstream branching; keeps provider-specific code contained. | Requires touching each provider adapter. |
| B | Keep string outputs but add sentinel prefixes for empty/error states. | Minimal code movement. | Fragile and easy for prompts to treat as evidence. |
| C | Raise typed exceptions for all empty/error paths. | Simple control flow for hard failures. | Empty search can be recoverable and should not always abort the whole report. |

## Recommended Plan

1. Implement Option A in the shared search utility layer.
2. Map every provider into `success`, `empty`, or `error` with enough detail for recovery.
3. Update planning and section-writing nodes to continue only on `success` with non-empty sources.
4. For `empty`, generate narrower follow-up queries or surface a section-specific missing-source message after the retry budget.
5. For `error`, retry transient provider failures or surface a clear provider failure instead of passing the error text to the writer.

## Acceptance Criteria

- [ ] Issue is linked to this PR.
- [ ] Search adapters return an explicit outcome instead of ambiguous report-source text for empty/error cases.
- [ ] Planning and writing do not treat empty/error messages as evidence.
- [ ] Users get a recoverable retry, fallback, or clear partial-failure path when sources are unavailable.
