# I-3: Supervisor prompt references non-existent enhanced_tavily_search tool

## Summary

**Context:** The multi-agent flow uses supervisor and researcher prompts to guide search-based research.

**Bug:** The prompts reference `enhanced_tavily_search` as the tool to use, but the tool registry only exposes `tavily_search` or `duckduckgo_search`. No tool named `enhanced_tavily_search` exists anywhere in the codebase.

**Actual vs. expected:** Model attempts to call `enhanced_tavily_search` → tool call fails or is skipped. Expected: model calls the actual registered tool.

**Impact:** Researchers in the multi-agent flow cannot perform web searches reliably, producing low-quality or empty research sections.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L263-L325" />

```python
# Line 264
"use the `enhanced_tavily_search` to collect relevant information"
# <-- BUG 🔴 Tool does not exist; should be tavily_search

# Line 324
"Begin with a SINGLE, well-crafted search query with `enhanced_tavily_search`"
# <-- BUG 🔴 Same non-existent tool reference
```

## Evidence

- `grep -r "enhanced_tavily" src/` only matches prompts.py (2 occurrences)
- Tool registration in multi_agent.py and utils.py defines `tavily_search` and `duckduckgo_search` only
- The model will attempt to call `enhanced_tavily_search`, which is not in the tool list

## Recommendation

Replace `enhanced_tavily_search` with `tavily_search` in prompts.py lines 264 and 324.

```python
# Line 264: change to
"use the `tavily_search` to collect relevant information"

# Line 324: change to
"Begin with a SINGLE, well-crafted search query with `tavily_search`"
```

**Optional improvement:** Make the tool name dynamic based on the configured `search_api` to avoid future drift.
