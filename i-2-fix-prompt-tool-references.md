# I-2: Supervisor and researcher prompts reference nonexistent tool and give contradictory search instructions

## Summary

**Context:** The multi-agent supervisor and researcher prompts guide the LLM on which tools to use and how many searches to perform.

**Bug:** Both prompts reference `enhanced_tavily_search` which does not exist in the bound tool set. The supervisor prompt also contradicts itself — it says "MUST perform ONLY ONE search" then later says "Use multiple searches to build a complete picture."

**Actual vs. expected:** The model should be directed to use the actual tool names (`tavily_search` or `duckduckgo_search`) with a consistent search policy.

**Impact:** Models attempting to call the nonexistent tool produce errors. Contradictory guidance causes inconsistent search behavior across runs, reducing report quality.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L263-L266" />

```python
# Supervisor prompt, step 1:
"use the `enhanced_tavily_search` to collect relevant information"
"You MUST perform ONLY ONE search to gather comprehensive context"
# <-- BUG 🔴 enhanced_tavily_search doesn't exist; actual tools are tavily_search / duckduckgo_search
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L303-L307" />

```python
# Supervisor prompt, additional notes:
"Use multiple searches to build a complete picture before drawing conclusions."
# <-- BUG 🔴 Contradicts "MUST perform ONLY ONE search" from step 1
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L324-L325" />

```python
# Researcher prompt:
"Begin with a SINGLE, well-crafted search query with `enhanced_tavily_search`"
# <-- BUG 🔴 Same nonexistent tool name
```

### Actual tool surface

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L90-L100" />

The supervisor and researcher are bound to `tavily_search` or `duckduckgo_search` (selected by config), plus the structured output tools (Sections, Introduction, Conclusion, Section).

## Evidence

### Nonexistent tool reference

The string `enhanced_tavily_search` appears 3 times in `prompts.py` (lines 263, 305 area, 324). The actual tool functions are:
- `tavily_search` (utils.py L1263-1305)
- `duckduckgo_search` (utils.py L1151-1261)

No function named `enhanced_tavily_search` exists anywhere in the codebase.

### Contradictory instructions

| Location | Instruction |
|----------|-------------|
| L265 | "You MUST perform ONLY ONE search" |
| L307 | "Use multiple searches to build a complete picture" |

These appear in the same prompt (SUPERVISOR_INSTRUCTIONS), creating an irreconcilable conflict for the model.

## Impact

- **Tool errors:** Models attempting `enhanced_tavily_search` get a tool-not-found error, wasting a turn and potentially confusing the agent loop
- **Inconsistency:** Contradictory search guidance means some runs do one search (shallow research) while others do many (higher cost, better quality) — the behavior is unpredictable
- **Quality:** Shallow single-search runs produce less comprehensive reports

## Recommendation

Two changes needed:

1. **Replace all `enhanced_tavily_search` references** with a generic reference like "the search tool" or dynamically inject the configured tool name
2. **Resolve the search count contradiction** — recommend allowing multiple targeted searches (the "multiple searches" instruction is more aligned with quality research)

### Suggested implementation

```python
# In prompts.py, update SUPERVISOR_INSTRUCTIONS:

# Step 1 - replace:
"use the `enhanced_tavily_search` to collect relevant information"
"You MUST perform ONLY ONE search"
# with:
"use the search tool to collect relevant information"
"Perform targeted searches to build context — each search should have a distinct focus"

# Additional notes - remove the contradiction by keeping only:
"Use multiple targeted searches to build a complete picture before drawing conclusions."

# In RESEARCH_INSTRUCTIONS, replace:
"Begin with a SINGLE, well-crafted search query with `enhanced_tavily_search`"
# with:
"Begin with a targeted search query that directly addresses the core of the section topic."
```

This is a straightforward find-and-replace in `prompts.py` — no architectural decisions needed.
