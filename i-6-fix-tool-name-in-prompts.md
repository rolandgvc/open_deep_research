# I-6: Multi-agent prompts reference non-existent tool enhanced_tavily_search

## Summary

**Context:** The multi-agent variant uses SUPERVISOR_INSTRUCTIONS and RESEARCH_INSTRUCTIONS prompts to guide research behavior, including which tools to call.

**Bug:** Both prompts reference `enhanced_tavily_search` (lines 264, 324 in prompts.py), but the multi-agent toolset only registers `tavily_search` and `duckduckgo_search` (multi_agent.py:13, 26).

**Actual vs. expected:** The model is instructed to call a tool that doesn't exist. Expected: prompts reference the actual registered tool names.

**Impact:** The model attempts to call `enhanced_tavily_search`, which either fails with a tool-not-found error or causes the model to skip searching entirely. Either way, the multi-agent variant's research capability is degraded.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L258-L335" />
<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L16-L35" />

```python
# prompts.py:264
"use the `enhanced_tavily_search` to collect relevant information"  # <-- BUG 🔴 Tool doesn't exist

# prompts.py:324
"Begin with a SINGLE, well-crafted search query with `enhanced_tavily_search`"  # <-- BUG 🔴 Same

# multi_agent.py:13 - actual imports
from open_deep_research.utils import get_config_value, tavily_search, duckduckgo_search
```

## Evidence

### Inconsistency

Prompts reference: `enhanced_tavily_search`
Registered tools: `tavily_search`, `duckduckgo_search`

The tool name mismatch means the model's tool-call schema won't include `enhanced_tavily_search`, leading to either:
1. A tool validation error if the model generates a call to the non-existent tool
2. The model choosing not to search because the instructed tool isn't available

## Impact

- **Functionality:** Multi-agent research variant is broken or severely degraded
- **User experience:** Reports generated via multi-agent lack research depth or fail entirely

## Recommendation

Replace `enhanced_tavily_search` with `tavily_search` in both prompt locations.

```python
# prompts.py:264 — change to:
"use the `tavily_search` to collect relevant information"

# prompts.py:324 — change to:
"Begin with a SINGLE, well-crafted search query with `tavily_search`"
```

This is a minimal 2-line fix with no decision points.
