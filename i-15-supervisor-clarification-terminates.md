# I-15: Multi-agent supervisor prompt requires clarification exchange but workflow terminates on non-tool output

## Summary

**Context:** The multi-agent supervisor is instructed to engage in at least one clarification exchange with the user before defining report sections.

**Bug:** `supervisor_should_continue` returns `END` when the model produces a non-tool-call message. Since clarification questions are plain text (not tool calls), asking a question terminates the entire graph.

**Actual vs. expected:** Supervisor asks a follow-up question → graph terminates with no report. Expected: graph pauses for user response, then continues.

**Impact:** Any run where the model follows the clarification instruction produces an incomplete or empty report instead of a clarification exchange.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L270-L275" />

```python
# Prompt says:
# "You MUST engage in at least one clarification exchange with the user before proceeding"
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L204-L216" />

```python
async def supervisor_should_continue(state: ReportState) -> Literal["supervisor_tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "supervisor_tools"
    else:
        return END  # <-- BUG 🔴 Terminates when supervisor asks a question
```

## Evidence

### Example

1. User submits topic: "Compare renewable energy policies across EU nations"
2. Supervisor performs one search (tool call → continues)
3. Supervisor asks: "Could you clarify which EU nations you're most interested in?" (plain text, no tool call)
4. `supervisor_should_continue` sees no tool calls → returns `END`
5. Graph terminates — user never gets to respond

### Inconsistency

The single-agent graph (`graph.py`) handles this via `human_feedback` interrupt node. The multi-agent graph has no equivalent mechanism.

## Impact

- **Correctness:** Reports are generated without user clarification even though the prompt requires it
- **UX:** Users may see a truncated output that is just the clarification question with no report

## Recommendation

**Decision needed:**

- Option A: Add a LangGraph `interrupt` node — when the supervisor outputs plain text (no tool calls), pause the graph and wait for user input. This aligns the graph with the prompt's intent. Requires client-side support for resuming the graph.
- Option B: Remove the clarification requirement from `SUPERVISOR_INSTRUCTIONS` — accept that the multi-agent graph is fire-and-forget and skip clarification. Simpler but reduces research quality.
- Option C: Convert clarification into a tool — create a `ClarificationQuestion` tool so the question is a tool call, and add a handler that interrupts for user input. Keeps the routing logic consistent.

### Suggested implementation (Option A)

```python
from langgraph.types import interrupt

async def supervisor_should_continue(state: ReportState) -> Literal["supervisor_tools", "wait_for_input", END]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "supervisor_tools"
    # Check if this looks like a question (heuristic or explicit flag)
    elif "?" in last_message.content:
        return "wait_for_input"
    else:
        return END

async def wait_for_input(state: ReportState):
    user_response = interrupt(state["messages"][-1].content)
    return {"messages": [{"role": "user", "content": user_response}]}
```

## Related

- I-2: `human_feedback` approval check in single-agent graph (same pattern, different flow)
- I-3: Supervisor prompt references non-existent `enhanced_tavily_search` tool (same prompt file)
