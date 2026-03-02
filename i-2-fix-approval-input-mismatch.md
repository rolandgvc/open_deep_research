# I-2: human_feedback approval check rejects valid string input, blocking plan acceptance

## Summary

**Context:** The `human_feedback` node in `graph.py` uses a LangGraph `interrupt()` to collect user approval or feedback on the generated report plan.

**Bug:** The prompt tells users to "Pass 'true'" (a string), but the code checks `isinstance(feedback, bool) and feedback is True`. LangGraph interrupts return user input as strings, so a user following the instructions sends string `"true"` which matches the `elif isinstance(feedback, str)` branch — treated as feedback to regenerate, not approval.

**Actual vs. expected:** User types `true` → plan is regenerated (wrong). Expected: plan is approved and section writing begins.

**Impact:** Users cannot approve a valid research plan and get stuck in repeated re-planning loops.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L159-L182" />

```python
feedback = interrupt(interrupt_message)

# If the user approves the report plan, kick off section writing
if isinstance(feedback, bool) and feedback is True:  # <-- BUG 🔴 Only matches Python bool True, never string "true"
    return Command(goto=[...])

elif isinstance(feedback, str):  # <-- String "true" lands here, treated as regeneration feedback
    return Command(goto="generate_report_plan",
                   update={"feedback_on_report_plan": feedback})
```

## Evidence

### Example

1. User submits research topic, plan is generated
2. LangGraph interrupt prompts: "Pass 'true' to approve the report plan."
3. User types `true` (string) as instructed
4. `isinstance("true", bool)` → False → skips approval branch
5. `isinstance("true", str)` → True → enters feedback branch
6. Plan is regenerated with feedback_on_report_plan="true"
7. User is stuck in a loop — no way to approve

## Recommendation

Normalize the feedback value to accept both boolean and string forms of "true":

### Suggested implementation

```python
feedback = interrupt(interrupt_message)

# Normalize: treat string "true" (case-insensitive) as approval
is_approved = (
    (isinstance(feedback, bool) and feedback is True) or
    (isinstance(feedback, str) and feedback.strip().lower() == "true")
)

if is_approved:
    return Command(goto=[
        Send("build_section_with_web_research", {"topic": topic, "section": s, "search_iterations": 0})
        for s in sections
        if s.research
    ])
elif isinstance(feedback, str):
    return Command(goto="generate_report_plan",
                   update={"feedback_on_report_plan": feedback})
else:
    raise TypeError(f"Interrupt value of type {type(feedback)} is not supported.")
```

This is a minimal, clear fix (< 10 lines changed). Can be implemented directly.
