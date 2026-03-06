# I-17: Research agent can exit without producing a Section, leaving silent gaps in the report

## Summary

**Context:** The research agent is a LangGraph subgraph that researches a topic and calls the `Section` tool to produce structured output. The supervisor dispatches one research agent per section.

**Bug:** `bind_tools` does not enforce tool usage (no `tool_choice`), and `research_agent_should_continue` returns `END` when no tool call is made. If the model responds with plain text instead of calling `Section`, the subgraph exits silently with no section output.

**Actual vs. expected:** Research subgraph terminates with no `completed_sections` entry. Expected: every research subgraph produces exactly one Section or raises an error.

**Impact:** The supervisor assembles reports with missing body sections. Users see unexplained gaps with no indication that content was dropped.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L231-L242" />

```python
async def research_agent(state: SectionState, config: RunnableConfig):
    llm = init_chat_model(model=researcher_model)
    research_tool_list, _ = get_research_tools(config)
    return {
        "messages": [
            await llm.bind_tools(research_tool_list).ainvoke(  # <-- No tool_choice enforcement
                [{"role": "system", "content": RESEARCH_INSTRUCTIONS.format(...)}]
                + state["messages"]
            )
        ]
    }
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L281-L292" />

```python
async def research_agent_should_continue(state: SectionState) -> Literal["research_agent_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "research_agent_tools"
    else:
        return END  # <-- BUG 🔴 Exits without checking if Section was produced
```

## Evidence

### Example

1. Supervisor sends section task: "Research renewable energy adoption rates in Nordic countries"
2. Research agent calls search tool → gets results → continues
3. On next turn, model responds with a plain-text summary instead of calling `Section` tool
4. `research_agent_should_continue` sees no tool calls → returns `END`
5. `completed_sections` for this subgraph is empty
6. Supervisor assembles report — this section is silently missing

### Inconsistency

The `research_agent_tools` function correctly checks for `Section` tool calls and stores them in `completed_sections`. But there is no validation that `completed_sections` is non-empty when the subgraph exits.

## Impact

- **Correctness:** Reports have missing sections with no error or warning
- **Reliability:** Output completeness depends on model behavior rather than graph enforcement
- **Debugging:** No signal that a section was dropped — hard to diagnose incomplete reports

## Recommendation

**Decision needed:**

- Option A: Use `tool_choice="required"` on the final research agent turn to force a tool call. Requires tracking iteration count to switch from `tool_choice="auto"` (for search) to `tool_choice="required"` (for final output).
- Option B: Add a validation gate — if `research_agent_should_continue` would return `END` but no Section was produced, re-invoke the agent with an explicit instruction to call the Section tool.
- Option C: Add a max-iterations counter and force `tool_choice={"type": "function", "function": {"name": "Section"}}` on the last allowed iteration.

### Suggested implementation (Option B)

```python
async def research_agent_should_continue(state: SectionState) -> Literal["research_agent_tools", "research_agent", END]:
    messages = state["messages"]
    last_message = messages[-1]
    
    if last_message.tool_calls:
        return "research_agent_tools"
    
    # Check if we have a completed section
    if not state.get("completed_sections"):
        # No section produced yet — retry with explicit instruction
        # Add a nudge message and loop back
        return "research_agent"  # Will need a retry counter to prevent infinite loops
    
    return END
```

This requires adding a retry counter to `SectionState` and appending a user message like "You must call the Section tool to complete your research" before re-invoking.

## Related

- I-16: Supervisor elif chain drops conclusion (downstream effect — even when sections are produced, assembly logic has its own issues)
