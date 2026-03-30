# No hard iteration cap on supervisor and researcher agent loops

## Summary

**Context:** The multi-agent graph uses a supervisor agent that delegates section research to parallel researcher subagents. Both the supervisor and each researcher run in LLM-governed loops.

**Bug:** Neither loop has a maximum-turn guard. Continuation is gated solely on whether the LLM's last message contains tool calls. There are no turn counters in `ReportState`, `SectionState`, or `Configuration`.

**Actual vs. expected:** On complex topics, the supervisor or researcher can loop past any reasonable budget. The first hard ceiling is LangGraph's default 25-step recursion limit, which triggers a `GraphRecursionError` crash — no partial output, no informative message to the user. Expected: configurable turn caps that route to the next pipeline stage gracefully when reached.

**Impact:** Unbounded token cost per run; hard crash rather than graceful degradation when the recursion limit is hit; no operational visibility into loop depth.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L155-L200" />

```python
def supervisor_should_continue(state: ReportState) -> str:
    last_message = state["messages"][-1]
    return "supervisor_tools" if last_message.tool_calls else END
    # <-- BUG: no turn counter; purely LLM-governed

def research_agent_should_continue(state: SectionState) -> str:
    last_message = state["messages"][-1]
    return "research_agent_tools" if last_message.tool_calls else END
    # <-- BUG: no turn counter; purely LLM-governed
```

`SUPERVISOR_INSTRUCTIONS` includes prose-only bounds:
```
You MUST perform ONLY ONE search before moving forward.
```
This provides no structural enforcement — the LLM may ignore it.

## Evidence

### Example

1. User submits a broad or underspecified topic ("AI safety").
2. Supervisor performs initial search, receives ambiguous results.
3. Supervisor issues another search tool call (ignoring the "ONLY ONE search" instruction).
4. Repeat until LangGraph's 25-step recursion limit is reached.
5. `GraphRecursionError` is raised — user receives no output and no meaningful error.

### Cost scenario

A 5-section report with 3 supervisor search rounds + 4 researcher iterations per section = 23 LLM calls before the graph crashes. Token cost is uncapped and invisible to the user.

## Impact

- **Reliability:** Hard crash on complex topics instead of graceful completion with partial output.
- **Cost:** Token spend is unbounded per run; no circuit breaker.
- **Operability:** No turn-count visibility in state makes it impossible to diagnose loop depth in production traces.

## Recommendation

Add configurable turn caps to `Configuration` and enforce them structurally in each routing function.

**Decision needed:**

- **Option A — State counters + routing:** Thread `supervisor_turn_count` into `ReportState` and `researcher_turn_count` into `SectionState`. Increment in each agent node. Check in `supervisor_should_continue` / `research_agent_should_continue` before the next LLM call. Route to the next pipeline stage gracefully when the cap is hit.
- **Option B — LangGraph recursion limit override:** Pass a higher `recursion_limit` in the graph config and rely on LangGraph's built-in ceiling. Simpler but still produces a crash rather than graceful degradation; does not add turn visibility.

Option A is strongly preferred — it provides both graceful degradation and operational observability.

### Suggested implementation (Option A)

```python
# configuration.py
@dataclass(kw_only=True)
class Configuration:
    ...
    max_supervisor_turns: int = field(default=15, metadata={"description": "Max supervisor loop iterations"})
    max_researcher_turns: int = field(default=6, metadata={"description": "Max researcher loop iterations per section"})

# multi_agent.py — add to state schemas
class ReportState(MessagesState):
    ...
    supervisor_turn_count: int  # initialize to 0

class SectionState(MessagesState):
    ...
    researcher_turn_count: int  # initialize to 0

# Updated routing functions
def supervisor_should_continue(state: ReportState, config: RunnableConfig) -> str:
    configurable = Configuration.from_runnable_config(config)
    if state.get("supervisor_turn_count", 0) >= configurable.max_supervisor_turns:
        # Log warning and proceed to next stage
        return END
    last_message = state["messages"][-1]
    return "supervisor_tools" if last_message.tool_calls else END

def research_agent_should_continue(state: SectionState, config: RunnableConfig) -> str:
    configurable = Configuration.from_runnable_config(config)
    if state.get("researcher_turn_count", 0) >= configurable.max_researcher_turns:
        return END
    last_message = state["messages"][-1]
    return "research_agent_tools" if last_message.tool_calls else END

# Increment counters in agent nodes (supervisor and research_agent)
```

## Related

- Workflow graph (`graph.py`) bounds search with `search_iterations >= configurable.max_search_depth` — the same pattern applied to the multi-agent graph resolves this gap.
- Finding: [Researcher can exit without writing a section] — a turn cap also limits the window in which a researcher can fail to produce output.
