# I-3: Fix contradictory search directives in SUPERVISOR_INSTRUCTIONS

## Summary

**Context:** The `SUPERVISOR_INSTRUCTIONS` prompt in `prompts.py` guides the supervisor model's behavior in the multi-agent flow.

**Bug:** Step 1 (line 265) says `"You MUST perform ONLY ONE search"` while Additional Notes (line 306) says `"Use multiple searches to build a complete picture before drawing conclusions."` These directly contradict each other.

**Impact:** The supervisor model receives conflicting signals, producing inconsistent research depth across runs — some reports have thin context (one search) while others perform redundant searches, wasting tokens and increasing latency.

## Where

`src/open_deep_research/prompts.py` lines 265 and 306

Step 1 mandates one search:
```python
# Line 265:
"You MUST perform ONLY ONE search to gather comprehensive context"
```

Additional Notes section says multiple:
```python
# Line 306:
"Use multiple searches to build a complete picture before drawing conclusions."
```

## Decision Needed

**Option A: Single search (current step 1 intent)**
- Remove line 306 (`"Use multiple searches..."`)
- Keeps token cost and latency low
- Relies on one well-crafted query for context gathering

**Option B: Multiple searches (current additional notes intent)**
- Change step 1 to: `"Perform 1-3 focused searches to gather comprehensive context"`
- Remove the `"ONLY ONE"` constraint
- Provides more thorough research but increases cost and latency

**Option C: Bounded multi-search with guidelines**
- Change step 1 to: `"Perform up to 3 targeted searches to gather comprehensive context. Start with a broad query, then follow up on specific gaps."`
- Update line 306 to: `"Use targeted follow-up searches only when initial results have clear gaps."`
- Balances thoroughness with efficiency

## Recommendation

Option C provides the best balance. The supervisor benefits from the ability to follow up when initial results are thin, but a bound prevents unbounded search loops.
