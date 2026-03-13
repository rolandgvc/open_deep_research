# I-1: Multi-agent supervisor and researcher can terminate without producing required artifacts

## Summary

**Context:** The multi-agent path uses a supervisor/researcher loop where `supervisor_should_continue` and `research_agent_should_continue` route the graph based on whether the last LLM message contains tool calls.

**Bug:** Both continuation functions treat *any* non-tool-call response as terminal success. Neither validates that the expected structured outputs (Sections, Introduction, Conclusion, Section) were actually produced before ending.

**Actual vs. expected:** The graph can silently end with no `Sections` plan, missing body sections, or no `final_report` — instead of either producing complete output or raising a recoverable error.

**Impact:** Users receive partial or empty output after expensive search calls have already been made, with no error signal.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L204-L216" />

```python
async def supervisor_should_continue(state: ReportState) -> Literal["supervisor_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "supervisor_tools"
    else:
        return END  # <-- BUG 🔴 No check that Sections/Introduction/Conclusion were ever produced
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L273-L282" />

```python
async def research_agent_should_continue(state: SectionState) -> Literal["research_agent_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "research_agent_tools"
    else:
        return END  # <-- BUG 🔴 No check that Section tool was called
```

## Evidence

### Scenario: Supervisor ends without creating sections

1. User submits topic "AI in healthcare"
2. Supervisor calls `tavily_search` to gather background
3. Supervisor responds with a plain-text summary instead of calling `Sections` tool
4. `supervisor_should_continue` sees no `tool_calls` → routes to `END`
5. `final_report` is never assembled; user gets empty or partial output

### Scenario: Researcher ends without writing section

1. Supervisor creates sections and dispatches to research team
2. Researcher calls search tools, gathers data
3. Researcher responds with prose summary instead of calling `Section` tool
4. `research_agent_should_continue` routes to `END`
5. That section is missing from the final report — no error raised

Both scenarios become more likely with model drift, temperature variation, or provider behavior changes.

## Impact

- **Reliability:** Silent failures waste compute (search calls already made) and produce incomplete output
- **User experience:** No error signal — users may not realize the report is incomplete
- **Cost:** Failed runs incur full search and LLM costs with no usable output

## Recommendation

Add output validation gates before terminal transitions.

**Decision needed:**

- Option A: **Validation gate with retry** — Check state for required artifacts before allowing END. If missing, re-invoke the agent with a message like "You must call the [Tool] tool before finishing." Cap retries at 2-3.
- Option B: **`tool_choice="required"`** — Force tool calls on critical turns (simpler but less flexible — the model must always call a tool, even when it legitimately wants to ask a clarifying question).
- Option C: **Hybrid** — Use `tool_choice="required"` only on the final turn (after search is done), and validation gates elsewhere.

### Suggested implementation (Option A)

```python
async def supervisor_should_continue(state: ReportState) -> Literal["supervisor_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        return "supervisor_tools"

    # Validate required artifacts before allowing termination
    if not state.get("final_report"):
        # Check if we have sections defined
        if not state.get("sections"):
            # Re-prompt: sections not yet defined
            return "supervisor_tools"  # or route to a "retry" node
        return "supervisor_tools"

    return END
```

## Related

- Existing PR "Add Section output guard to research agent subgraph" covers the researcher side partially but does not address the supervisor path.
