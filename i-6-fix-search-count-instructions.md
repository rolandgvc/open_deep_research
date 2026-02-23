# I-6: Contradictory search count instructions in supervisor prompt

## Summary

**Context:** `SUPERVISOR_INSTRUCTIONS` in `prompts.py` guides the supervisor on how to scope research, including how many searches to perform.

**Bug:** Step 1 says "You MUST perform ONLY ONE search" while Additional Notes says "Use multiple searches to build a complete picture" — directly contradictory.

**Actual vs. expected:** The model receives two conflicting directives in the same prompt. Depending on where attention lands, it follows one or the other inconsistently.

**Impact:** Non-deterministic research behavior — identical topics produce different search counts across runs, leading to either under-researched or over-cost reports.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L257-L307" />

Step 1 (~line 265):
```python
# "You MUST perform ONLY ONE search to gather comprehensive context"
```

Additional Notes (~line 305):
```python
# "Use multiple searches to build a complete picture before drawing conclusions."
```

## Evidence

These are direct contradictions within the same prompt block. The supervisor will:
1. Sometimes follow Step 1 (one search) → under-researched reports
2. Sometimes follow Additional Notes (multiple searches) → higher latency and token cost
3. Behavior varies across runs on the same topic

## Impact

- **Quality:** Under-researched reports when single-search path is taken
- **Cost:** Unnecessary API spend when multiple-search path is taken
- **Predictability:** Users cannot reason about expected research behavior or cost

## Recommendation

**Decision needed:**

- **Option A: Single search** — Remove "Use multiple searches..." from Additional Notes. Keep the focused one-search approach in Step 1. Simpler, cheaper, more predictable.
- **Option B: Bounded multiple searches** — Replace both lines with "Perform 1–3 targeted searches to gather comprehensive context." Remove the "ONLY ONE" constraint. Better coverage but higher cost.
- **Option C: Multiple searches (current Additional Notes intent)** — Remove "ONLY ONE" from Step 1. Let the supervisor decide search count. Most flexible but least predictable.

### Suggested implementation (Option B)

In `prompts.py`, Step 1:
```python
# Replace:
#   "You MUST perform ONLY ONE search to gather comprehensive context"
# With:
#   "Perform 1-3 targeted searches to gather comprehensive context"
```

In Additional Notes, remove:
```python
# Remove: "Use multiple searches to build a complete picture before drawing conclusions."
```

## Related

- I-5: Same prompt file has non-existent tool name references (separate fix)
