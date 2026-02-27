# I-2: Fix supervisor prompt — non-existent tool reference and contradictory search directives

## Summary

**Context:** The supervisor prompt in `SUPERVISOR_INSTRUCTIONS` guides the LLM through research topic clarification, search, and report structure creation.

**Bug:** Two conflicts: (1) the prompt references `enhanced_tavily_search` which doesn't exist in the registered toolset, and (2) line 265 says "MUST perform ONLY ONE search" while line 306 says "Use multiple searches to build a complete picture."

**Actual vs. expected:** The LLM is told to call a tool that doesn't exist and given contradictory search count guidance. Expected: instructions match available tools and give consistent direction.

**Impact:** Tool-call errors or silently skipped searches when the model can't find `enhanced_tavily_search`. Inconsistent research depth across runs due to contradictory directives.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L264-L266" />

```python
# Line 264 — references non-existent tool
Based upon the user's topic, use the `enhanced_tavily_search` to collect relevant information about the topic.
# <-- BUG 🔴 Only `tavily_search` and `duckduckgo_search` are registered in multi_agent.py L13-L28
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L265" />

```python
# Line 265
- You MUST perform ONLY ONE search to gather comprehensive context
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L306" />

```python
# Line 306 — contradicts line 265
- Use multiple searches to build a complete picture before drawing conclusions.
# <-- BUG 🔴 Contradicts "ONLY ONE search" directive above
```

Also at line 324:

```python
a) **First Query**: Begin with a SINGLE, well-crafted search query with `enhanced_tavily_search`
# <-- BUG 🔴 Same non-existent tool name
```

## Evidence

### Tool mismatch

`multi_agent.py` L13-L28 registers only:
- `tavily_search` (when `SearchAPI.TAVILY`)
- `duckduckgo_search` (when `SearchAPI.DUCKDUCKGO`)

No `enhanced_tavily_search` exists anywhere in the codebase outside of prompts.py.

### Contradictory search count

- L265: "You MUST perform ONLY ONE search"
- L306: "Use multiple searches to build a complete picture"

These are in the same prompt block, giving the model conflicting signals.

## Impact

- **Tool errors:** LLM attempts to call `enhanced_tavily_search`, gets a tool-not-found error, and either retries or skips searching entirely — both degrade research quality.
- **Inconsistent depth:** Depending on which directive the model follows, research runs vary from single shallow searches to many redundant searches.

## Recommendation

**Fix 1 — Tool name:** Replace all references to `enhanced_tavily_search` with the actual search tool function name. Consider using a placeholder like `{search_tool}` that gets formatted at runtime based on configuration.

**Fix 2 — Search count:** Unify into a single directive, e.g.:
> "Begin with one broad search to understand the topic. Follow up with targeted searches as needed, up to a maximum of 3 searches per section."

### Suggested implementation

```python
# prompts.py L264 — replace enhanced_tavily_search
Based upon the user's topic, use the search tool to collect relevant information about the topic.
   - Begin with one broad search to understand the topic
   - Follow up with up to 2 targeted searches if needed for depth
   - Take time to analyze and synthesize the search results before proceeding

# prompts.py L306 — remove contradictory line or align
- Use targeted follow-up searches to fill gaps, but avoid redundant queries.

# prompts.py L324 — fix tool name
a) **First Query**: Begin with a SINGLE, well-crafted search query that directly addresses the core of the section topic.
```

## Related

- The `RESEARCH_INSTRUCTIONS` prompt at L324 also references `enhanced_tavily_search` — same fix needed there.
