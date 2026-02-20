# I-2: Supervisor clarification questions terminate the multi-agent run

## Summary

**Context:** The supervisor prompt requires asking the user at least one clarification question before proceeding with research.

**Bug:** The multi-agent control flow ends whenever the latest supervisor message lacks tool calls, which includes clarification questions.

**Actual vs. expected:** The run terminates immediately after the supervisor asks a clarification question instead of waiting for a user response.

**Impact:** Reports can terminate without any output when the supervisor follows the prompt guidance.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/prompts.py#L270-L275" />
<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L204-L216" />

```python
# prompts.py
"""
You MUST ask at least one clarification question before proceeding.
"""
# <-- BUG 🔴 Prompt requires an interactive exchange
```

```python
# multi_agent.py
if not last_message.tool_calls:
    return "end"
# <-- BUG 🔴 Clarification questions trigger end-of-run
```

## Evidence

### Example

1. Supervisor asks, "Do you want the report focused on policy or technical details?"
2. The message has no tool calls.
3. supervisor_should_continue returns "end", terminating the graph before any research.

### Inconsistency

- Prompt requires a user clarification.
- Graph has no interrupt/resume path to collect a user reply.

## Impact

- **Reliability:** Some runs stop without producing a report.
- **User experience:** Users see a question but cannot respond in the same run.

## Recommendation

Add a human-in-the-loop interrupt/resume step or relax the prompt requirement.

**Decision needed:**

- Option A: Add a clarification node that pauses the graph until user input is provided.
- Option B: Remove the mandatory clarification requirement and allow the supervisor to proceed.

### Suggested implementation (Option A)

```python
# Pseudocode: detect clarification intent and yield control for user input
if supervisor_message_is_clarification:
    return "await_user"
```

## Related

None.
