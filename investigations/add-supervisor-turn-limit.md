# Add application-level turn limit to multi-agent supervisor loop

## Summary

**Context:** The multi-agent graph (`multi_agent.py`) uses a supervisor that delegates section research to a researcher agent. Both the supervisor and the researcher loop until the LLM stops producing tool calls.

**Bug:** Neither `supervisor_should_continue` nor `research_agent_should_continue` has an application-level iteration cap. The only termination guard is LangGraph's platform-level `recursion_limit` (default: 25 steps), which fires `GraphRecursionError` — crashing the run with no partial output and no user-friendly message.

**Actual vs. expected:**
- Actual: A supervisor that overproduces tool calls (due to prompt drift, ambiguous topic, or malformed API response) crashes with `GraphRecursionError` after 25 steps with no partial report.
- Expected: The graph exits gracefully after a configurable number of turns, returns whatever sections were completed, and surfaces a clear message.

**Impact:** Users running broad or ambiguous research topics receive a hard crash instead of a partial report. Token cost scales linearly with `recursion_limit` before termination.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L204-L215" />

```python
async def supervisor_should_continue(state: ReportState) -> Literal["supervisor_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        return "supervisor_tools"   # <-- No turn counter, no max-turns cap
    else:
        return END
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L281-L292" />

```python
async def research_agent_should_continue(state: SectionState) -> Literal["research_agent_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        return "research_agent_tools"  # <-- Same issue in researcher loop
    else:
        return END
```

The workflow graph (`graph.py`) uses `max_search_depth` as a hard guard — the multi-agent path has no equivalent.

## Evidence

### Example

1. User invokes multi-agent graph with a broad topic and `search_api = "tavily"`.
2. Supervisor model returns tool calls for more research on every turn (ambiguous topic keeps generating new angles).
3. No application-level cap exists — the graph runs until LangGraph's `recursion_limit` (default 25) is reached.
4. LangGraph raises `GraphRecursionError`. No partial sections are returned. The user sees an unhandled exception.

### Comparison with workflow graph

`graph.py` has:
```python
if state["search_iterations"] >= state["max_search_depth"]:
    return "write_section"  # graceful exit with partial results
```

The multi-agent path has no equivalent.

## Impact

- **Reliability:** Runaway supervisor crashes the entire run with no partial output.
- **Cost:** Token spend scales to `recursion_limit × avg_tokens_per_turn` before termination.
- **User experience:** Error is a raw platform exception, not a graceful message.

## Recommendation

Add a `supervisor_turn_count` field to `ReportState` and a `max_supervisor_turns` field to `Configuration`. Increment on each pass through `supervisor`. Exit gracefully when the cap is reached.

**Decision needed:**

- **Option A: Add turn counter to ReportState + configurable cap in Configuration**
  - Increment `supervisor_turn_count` in the `supervisor` node.
  - `supervisor_should_continue` returns `END` (with partial results) when count ≥ cap.
  - Add `max_supervisor_turns: int = 10` to `Configuration`.
  - Cleanest solution — mirrors `max_search_depth` in the workflow graph.

- **Option B: Set LangGraph `recursion_limit` via config + catch GraphRecursionError**
  - Pass `{"recursion_limit": configurable.max_supervisor_turns * 2}` in graph invocation.
  - Wrap graph invocation in try/except to extract partial `completed_sections` from state.
  - Less invasive but relies on LangGraph internals and partial state access after exception.

- **Option C: Add max_messages check inside supervisor_should_continue**
  - Count `tool_calls` messages in `state["messages"]` to approximate turn count.
  - No new state field needed, but message counting is fragile and doesn't map cleanly to "turns."

Option A is recommended — explicit state is more readable, testable, and mirrors the existing workflow graph pattern.

### Suggested implementation (Option A)

```python
# configuration.py — add field
max_supervisor_turns: int = field(default=10)

# multi_agent.py — update ReportState
class ReportState(MessagesState):
    sections: list[str]
    completed_sections: Annotated[list, operator.add]
    final_report: str
    supervisor_turn_count: int  # <-- new

# multi_agent.py — increment in supervisor node
async def supervisor(state: ReportState, config: RunnableConfig):
    ...
    return {
        "messages": [...],
        "supervisor_turn_count": state.get("supervisor_turn_count", 0) + 1,
    }

# multi_agent.py — cap in routing function
async def supervisor_should_continue(state: ReportState) -> Literal["supervisor_tools", END]:
    configurable = Configuration.from_runnable_config(...)  # need config here
    max_turns = get_config_value(configurable.max_supervisor_turns)
    if state.get("supervisor_turn_count", 0) >= max_turns:
        return END  # graceful exit with whatever sections are completed
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "supervisor_tools"
    return END
```

Note: `supervisor_should_continue` currently does not receive `config`. To pass configuration, either (a) convert it to a node that returns a `Command`, or (b) read `max_supervisor_turns` from `ReportState` directly (set it once at graph start from config). Option (b) avoids the function signature change.

## Related

- `graph.py:search_iterations` / `max_search_depth` — the workflow graph's equivalent pattern to follow.
- `research_agent_should_continue` in `multi_agent.py` — same issue applies to the researcher loop inside each section subgraph; consider adding `max_research_turns` as well.
