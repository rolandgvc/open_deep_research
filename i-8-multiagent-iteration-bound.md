# I-8: Multi-agent research loop has no iteration bound

## Summary

**Context:** The graph workflow bounds research iterations per section via `max_search_depth` (default: 2). When reached, `write_section` publishes the best available content.

**Bug:** The multi-agent variant has no equivalent bound. The `research_agent` → `research_agent_tools` → `research_agent` loop continues until the LLM decides to call the `Section` tool, or LangGraph hits its default recursion limit (25 steps).

**Actual vs. expected:** Unbounded iterations with an ungraceful `GraphRecursionError` crash. Expected: configurable iteration limit with best-effort content publication.

**Impact:** Unbounded search API calls and LLM tokens consumed per section, followed by a crash that returns no content.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L281-L310" />

```python
# research_agent_should_continue — no iteration check
async def research_agent_should_continue(state: SectionState) -> Literal["research_agent_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "research_agent_tools"  # <-- BUG 🔴 No iteration counter, loops unbounded
    else:
        return END
```

Compare with graph workflow (`graph.py:311-327`):

```python
# Graph workflow — bounded with best-effort fallback
if feedback.grade == "pass" or state["search_iterations"] >= configurable.max_search_depth:
    # Publish content even if max depth reached
```

## Evidence

### Comparison

| Feature | Graph workflow | Multi-agent |
|---------|---------------|-------------|
| Iteration bound | `max_search_depth` (default: 2) | None |
| Backstop | Graceful publish | `GraphRecursionError` at step 25 |
| Output on limit | Best-effort section | No section content |

### Cost scenario

If a research agent makes 3 search + 3 LLM calls per iteration × 25 iterations before recursion crash:
- 75 search API calls per stuck section (vs 6 with max_search_depth=2)
- 75 LLM inference calls per stuck section
- Zero usable output

## Impact

- **Cost:** Unbounded API consumption per section before crash
- **Reliability:** Ungraceful `GraphRecursionError` instead of controlled completion
- **Data loss:** No section content returned despite potentially valuable intermediate research

## Recommendation

Add a configurable `max_research_iterations` to `SectionState`.

**Decision needed:**

- Option A: Track iteration count in state, force `Section` tool call when limit reached
- Option B: Include iteration count in research agent prompt to encourage convergence (soft limit)
- Option C: Both — soft prompt guidance + hard state-based limit

### Suggested implementation (Option A)

```python
# Add to SectionState
class SectionState(MessagesState):
    section: Section
    completed_sections: Annotated[list, operator.add]
    search_iterations: int  # NEW: track iterations

# Update research_agent_should_continue
async def research_agent_should_continue(state: SectionState) -> Literal["research_agent_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    configurable = Configuration.from_runnable_config(config)

    if state.get("search_iterations", 0) >= configurable.max_search_depth:
        return END  # Force completion

    if last_message.tool_calls:
        return "research_agent_tools"
    else:
        return END
```

## Related

- Graph workflow `write_section` implements the bounded pattern (graph.py:311-327)
- `Configuration.max_search_depth` already exists, can be reused
