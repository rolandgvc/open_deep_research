# I-4: Add iteration bounds to multi-agent tool loops

## Summary

**Context:** The multi-agent variant (`multi_agent.py`) uses a supervisor agent that delegates to research agents, each running in a tool-calling loop (search → analyze → search → ... → write section).

**Bug:** `supervisor_should_continue` and `research_agent_should_continue` only check whether tool calls are present — there is no explicit iteration cap, step counter, or cost budget. The graphs are compiled without a `recursion_limit` parameter.

**Impact:** A model that keeps issuing search tool calls (due to insufficient results, prompt misalignment, or API returning empty results) can run up to LangGraph's default recursion limit of 25 steps per subgraph. Across 5+ sections, this permits potentially hundreds of search API calls and LLM invocations with no user-visible feedback or early termination.

## Where

```python
# multi_agent.py L204-216 — supervisor loop control
async def supervisor_should_continue(state: ReportState) -> Literal["supervisor_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "supervisor_tools"    # <-- No iteration check
    else:
        return END

# multi_agent.py L281-292 — research agent loop control
async def research_agent_should_continue(state: SectionState) -> Literal["research_agent_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "research_agent_tools"  # <-- No iteration check
    else:
        return END
```

Neither graph compilation sets `recursion_limit`:

```python
# multi_agent.py L316
research_builder.compile()  # No recursion_limit

# multi_agent.py L331  
graph = supervisor_builder.compile()  # No recursion_limit
```

## Evidence

- Both `should_continue` functions are pure tool-call presence checks
- No step counter tracked in `SectionState` or `ReportState`
- No `recursion_limit` parameter in either `compile()` call
- LangGraph default recursion_limit is 25, which still permits expensive runs

## Impact

- **Cost:** 25 iterations × (search API call + LLM call) × 5 sections = up to 250 API calls per report in worst case
- **Latency:** Unbounded loops can run for tens of minutes without producing useful output
- **User experience:** No indication that the agent is looping without progress

## Recommendation

### Option A: Explicit iteration counter in state (recommended)

Track iterations in state and enforce a cap:

```python
async def research_agent_should_continue(state: SectionState) -> Literal["research_agent_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    
    # Count research iterations (tool call messages from this agent)
    tool_call_count = sum(1 for m in messages if hasattr(m, 'tool_calls') and m.tool_calls)
    
    if tool_call_count >= MAX_RESEARCH_ITERATIONS:  # e.g., 8
        logger.warning(f"Research agent hit iteration limit ({MAX_RESEARCH_ITERATIONS})")
        return END
    
    if last_message.tool_calls:
        return "research_agent_tools"
    else:
        return END
```

### Option B: Set recursion_limit on graph compilation (simpler)

```python
graph = supervisor_builder.compile(recursion_limit=15)
```

### Option C: Both (belt and suspenders)

Combine explicit iteration tracking with a recursion_limit safety net.

**Decision needed:** Appropriate iteration cap per section (suggested: 5-8 research iterations) and whether to add a `recursion_limit` on the graph as a safety net.
