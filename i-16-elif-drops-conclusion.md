# I-16: Supervisor elif chain silently drops Conclusion when Introduction is also present

## Summary

**Context:** `supervisor_tools` processes all tool calls from the supervisor, then routes based on which tools were called (Sections, Introduction, or Conclusion).

**Bug:** The routing uses an `if/elif/elif` chain where `sections_list` > `intro_content` > `conclusion_content`. When Introduction and Conclusion are both called in one turn, only the Introduction branch executes — the Conclusion is stored in `conclusion_content` but never used.

**Actual vs. expected:** Reports assembled without conclusions when both tools fire in one turn. Expected: both are processed and the report is assembled with all parts.

**Impact:** Final reports can be missing conclusions with no error signal. Extra LLM turns needed to regenerate, increasing latency and token cost.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L185-L201" />

```python
# After processing all tool calls, decide what to do next
if sections_list:
    return Command(goto=[Send("research_team", {"section": s}) for s in sections_list], update={"messages": result})
elif intro_content:  # <-- BUG 🔴 If intro AND conclusion both present, conclusion is dropped
    result.append({"role": "user", "content": "Introduction written. Now write a conclusion section."})
    return Command(goto="supervisor", update={"final_report": intro_content, "messages": result})
elif conclusion_content:  # Unreachable when intro_content is also truthy
    intro = state.get("final_report", "")
    body_sections = "\n\n".join([s.content for s in state["completed_sections"]])
    complete_report = f"{intro}\n\n{body_sections}\n\n{conclusion_content}"
    ...
```

## Evidence

### Example

1. Supervisor decides to write both intro and conclusion in one turn
2. Model calls `Introduction(name="Overview", content="...")` and `Conclusion(name="Summary", content="...")`
3. Both tool calls are processed: `intro_content` and `conclusion_content` are set
4. Routing hits `elif intro_content` first → stores intro, prompts "Now write a conclusion section"
5. `conclusion_content` from this turn is silently discarded
6. Supervisor must re-generate conclusion in the next turn (if it does at all)

### Inconsistency

The tool processing loop correctly handles all tool calls (lines 155-183), but the routing logic assumes mutual exclusivity that the model may not respect.

## Impact

- **Correctness:** Reports may lack conclusions entirely
- **Cost:** Wasted tokens re-generating conclusions that were already produced
- **Reliability:** Output quality depends on model tool-calling behavior rather than robust control flow

## Recommendation

Replace the `elif` chain with logic that handles all combinations.

**Decision needed:**

- Option A: Store both intro and conclusion, assemble report immediately when all parts are present
- Option B: Force sequential tool calls using `tool_choice` so only one tool fires per turn (simpler but slower)

### Suggested implementation (Option A)

```python
# After processing all tool calls, decide what to do next
if sections_list:
    return Command(goto=[Send("research_team", {"section": s}) for s in sections_list], update={"messages": result})

# Store whatever was produced
update = {"messages": result}
if intro_content:
    update["final_report"] = intro_content
if conclusion_content:
    update["conclusion"] = conclusion_content

# Check if we have all parts to assemble
current_intro = intro_content or state.get("final_report", "")
current_conclusion = conclusion_content or state.get("conclusion", "")

if current_intro and current_conclusion and state.get("completed_sections"):
    body_sections = "\n\n".join([s.content for s in state["completed_sections"]])
    complete_report = f"{current_intro}\n\n{body_sections}\n\n{current_conclusion}"
    update["final_report"] = complete_report
    result.append({"role": "user", "content": "Report is now complete."})
    return Command(goto="supervisor", update=update)

# Otherwise prompt for missing parts
if intro_content and not current_conclusion:
    result.append({"role": "user", "content": "Introduction written. Now write a conclusion section."})
elif conclusion_content and not current_intro:
    result.append({"role": "user", "content": "Conclusion written. Now write an introduction."})

return Command(goto="supervisor", update=update)
```

Note: This requires adding a `conclusion` field to `ReportState`.

## Related

- I-15: Supervisor clarification terminates graph (same function, different control-flow issue)
