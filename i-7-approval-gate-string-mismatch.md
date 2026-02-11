# I-7: Human approval gate rejects string "true" despite prompt instructing it

## Summary

**Context:** The `human_feedback` node pauses the workflow via `interrupt()` to get user approval of the report plan before proceeding to section research.

**Bug:** The interrupt prompt tells users to "Pass 'true' to approve the report plan," but the handler only accepts `isinstance(feedback, bool) and feedback is True`. Any string input — including the string `"true"` — hits the `elif isinstance(feedback, str)` branch and is treated as revision feedback, triggering replanning.

**Actual vs. expected:** Users who type `true` (a string) get stuck in a plan→feedback→replan loop. Expected: the string `"true"` should be accepted as approval.

**Impact:** Users following the prompt instructions literally cannot progress past the planning phase.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L131-L180" />

```python
# Line 162 — prompt tells user to pass string
interrupt_message = f"""...Pass 'true' to approve the report plan..."""

feedback = interrupt(interrupt_message)

# Line 168 — only accepts boolean True
if isinstance(feedback, bool) and feedback is True:  # <-- BUG 🔴 String "true" fails this check
    return Command(goto=[...])  # approve

elif isinstance(feedback, str):  # <-- String "true" lands here
    return Command(goto="generate_report_plan", ...)  # treated as feedback!
```

## Evidence

### Example

1. User submits topic "AI in healthcare"
2. Workflow generates 5-section plan and interrupts for feedback
3. Prompt displays: "Pass 'true' to approve the report plan."
4. User types `true` via `Command(resume="true")`
5. `isinstance("true", bool)` → `False`, skips approval branch
6. `isinstance("true", str)` → `True`, enters feedback branch
7. Workflow regenerates plan with `"true"` as feedback text
8. User sees the same prompt again — stuck in loop

## Impact

- **Usability:** Users cannot approve the plan by following the displayed instructions
- **Workaround dependency:** Users must know to pass a Python boolean (client-dependent, not documented)

## Recommendation

Accept string approvals alongside boolean True.

**Decision needed:**

- Option A: Accept string inputs — check `feedback.lower() in ("true", "yes", "approve", "ok")` before the string branch
- Option B: Change the prompt to say "Approve the plan or provide feedback to revise it" and rely on boolean from client
- Option C: Both — accept strings and update prompt for clarity

### Suggested implementation (Option A)

```python
feedback = interrupt(interrupt_message)

# Accept boolean True or common approval strings
if isinstance(feedback, bool) and feedback is True:
    # Boolean approval
    return Command(goto=[...])
elif isinstance(feedback, str) and feedback.strip().lower() in ("true", "yes", "approve", "ok"):
    # String approval
    return Command(goto=[...])
elif isinstance(feedback, str):
    # Treat as revision feedback
    return Command(goto="generate_report_plan", update={"feedback_on_report_plan": feedback})
```
