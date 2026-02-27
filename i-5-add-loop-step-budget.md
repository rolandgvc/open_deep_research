# I-5: Add step budget to supervisor and researcher agent loops

## Summary

**Context:** The supervisor and researcher agent loops in `multi_agent.py` continue until the LLM produces a message with no tool calls.

**Bug:** Neither loop has an explicit step counter. When the LLM loops excessively (repeated clarifications, retried tool calls, or prompt conflicts causing oscillation), it hits LangGraph's default recursion limit of 25 and raises an unhandled `GraphRecursionError`.

**Actual vs. expected:** Users see an opaque error with no partial result. Expected: the loop exits gracefully after a reasonable number of steps, returning whatever partial work was completed.

**Impact:** Users get an unrecoverable error instead of a partial research report.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L204-L215" />

```python
async def supervisor_should_continue(state: ReportState) -> Literal["supervisor_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "supervisor_tools"
    else:
        return END
# <-- BUG 🔴 No step counter — relies on LangGraph default recursion limit (25)
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L281" />

```python
async def research_agent_should_continue(state: SectionState) -> Literal["research_agent_tools", END]:
    # Same pattern — no step tracking
```

## Evidence

- Neither function references `max_steps`, `step_count`, or any iteration tracking.
- No `recursion_limit` is explicitly set on graph compilation.
- The prompt conflicts in I-2 (contradictory "one search" vs "multiple searches") increase the likelihood of the supervisor oscillating and consuming iterations.

## Impact

- **User-visible error:** `GraphRecursionError` is not caught, producing an opaque stack trace instead of a useful result.
- **No partial recovery:** Any work completed before hitting the limit is lost.
- **Interaction with prompt conflicts:** The contradictory search directives (I-2) make excessive looping more likely.

## Recommendation

**Decision needed:**

- **Option A: Step counter in state** — Add `supervisor_steps: int` to `ReportState` and `researcher_steps: int` to `SectionState`. Increment in each node. Guard in `should_continue` with a configurable `max_steps` (e.g., 10 for supervisor, 5 for researcher). On limit, route to END.
- **Option B: Explicit recursion limit + catch** — Set `graph.compile(recursion_limit=15)` and wrap the graph invocation in a try/except for `GraphRecursionError`, returning a graceful partial result.

Option A is preferred — it gives finer control and allows returning partial results naturally.

### Suggested implementation (Option A)

```python
# In ReportState, add:
supervisor_steps: int = 0

# In supervisor node, increment:
state["supervisor_steps"] += 1

# In supervisor_should_continue:
MAX_SUPERVISOR_STEPS = 10
if state.get("supervisor_steps", 0) >= MAX_SUPERVISOR_STEPS:
    logger.warning("Supervisor hit step limit, finishing with current state")
    return END
if last_message.tool_calls:
    return "supervisor_tools"
return END
```

Apply the same pattern to `research_agent_should_continue` with a lower limit (e.g., 5).
