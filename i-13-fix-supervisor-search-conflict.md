# I-13: Supervisor prompt gives contradictory search directives

## Summary

**Context:** The `SUPERVISOR_INSTRUCTIONS` prompt in `prompts.py` controls the supervisor's research behavior in the multi-agent flow — including how many searches to perform before structuring the report.

**Bug:** Step 1 says "You MUST perform ONLY ONE search" while the Additional Notes section says "Use multiple searches to build a complete picture."

**Actual vs. expected:** The model non-deterministically follows one directive or the other, producing inconsistent research depth across runs.

**Impact:** Users get varying report quality — some runs are shallow (single search), others spend unnecessary API calls on extra searches. The inconsistency is not user-controllable.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L263-L266" />

```python
# Step 1 directive:
#    "You MUST perform ONLY ONE search to gather comprehensive context"
# <-- CONFLICT 🔴 with Additional Notes below
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L305-L306" />

```python
# Additional Notes:
#    "Use multiple searches to build a complete picture before drawing conclusions."
# <-- CONFLICT 🔴 contradicts the ONLY ONE directive above
```

## Evidence

These two directives are mutually exclusive within the same prompt. The model must choose which to follow, and the choice varies per run.

## Impact

- **Quality:** Inconsistent research depth across runs for the same topic
- **Cost:** Extra searches when the model follows the "multiple searches" directive unnecessarily
- **UX:** Users cannot predict or control the behavior

## Recommendation

Unify the search directives. The most likely intent:

**Decision needed:**

- Option A: Step 1 is a **single scoping search**, then researchers do deeper multi-search later — remove "Use multiple searches" from supervisor notes (it may belong in `RESEARCH_INSTRUCTIONS` instead)
- Option B: Allow **multiple supervisor searches** — remove the "ONLY ONE" constraint from step 1

### Suggested implementation (Option A)

```python
# In SUPERVISOR_INSTRUCTIONS step 1, keep:
#   "You MUST perform ONLY ONE search to gather comprehensive context"
#
# In Additional Notes, replace:
#   "Use multiple searches to build a complete picture before drawing conclusions."
# with:
#   "Your single search should be broad enough to scope the topic. Researchers will do deeper investigation."
```

## Related

- Issue #3: Supervisor prompt also references non-existent `enhanced_tavily_search` tool
