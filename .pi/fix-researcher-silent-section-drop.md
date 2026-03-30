# Researcher agent can exit without writing a section, silently truncating the final report

## Summary

**Context:** In the multi-agent graph, the supervisor dispatches one researcher subagent per planned section. Each researcher is expected to search for information and call the `Section` tool to record its output. The supervisor then assembles all sections into the final report.

**Bug:** `research_agent_should_continue` returns `END` on any no-tool-call message, regardless of whether the `Section` tool was ever called. If a researcher exits after search-only iterations without producing a section, `completed_sections` in `SectionOutputState` is never populated for that section. The supervisor has no validation step — it proceeds directly to writing introduction and conclusion with a shorter section list.

**Actual vs. expected:** A section silently disappears from the final report. Expected: the supervisor detects the missing section and either retries, injects a placeholder, or notifies the user.

**Impact:** Users receive a shorter-than-planned report with no indication that a section was dropped. The gap is invisible — only by comparing the planned outline to the delivered report would a user notice.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L195-L230" />

```python
def research_agent_should_continue(state: SectionState) -> str:
    last_message = state["messages"][-1]
    return "research_agent_tools" if last_message.tool_calls else END
    # <-- BUG: returns END without checking if Section tool was ever called

async def research_agent_tools(state: SectionState, config: RunnableConfig):
    ...
    for tool_call in tool_calls:
        if tool_call["name"] == "Section":
            completed_section = Section(**tool_call["args"])
            # only populated when Section is explicitly called
    return {"completed_sections": [completed_section] if completed_section else []}
    # <-- empty list returned silently if researcher exits without Section call
```

The `research_team` node returns to the supervisor with an empty `completed_sections` contribution. No supervisor node validates the count before proceeding.

Note: `compile_final_report` in `graph.py` is **not** used by the multi-agent graph — the supervisor assembles the report via `"\n\n".join(...)` over `state["completed_sections"]`, so the failure is silent truncation rather than a crash.

## Evidence

### Example

1. Supervisor plans a 5-section report on "quantum computing applications."
2. Four researchers complete their sections successfully.
3. Researcher 5 receives low-quality search results and emits a final message with no tool calls.
4. `research_agent_should_continue` returns `END` for researcher 5.
5. `research_team` returns with 4 completed sections.
6. Supervisor proceeds to write introduction and conclusion over 4 sections.
7. User receives a 4-section report. No warning, no placeholder, no retry.

## Impact

- **Data quality:** Final report silently omits one or more planned sections.
- **User trust:** Users have no way to know the report is incomplete without comparing the outline to the output.
- **Compounding risk:** Combined with no loop cap (related finding), a researcher can exhaust its budget without producing output and exit silently.

## Recommendation

Add a validation step after `research_team` that detects missing sections before synthesis begins.

**Decision needed:**

- **Option A — Post-research_team validation node:** Add a new node `validate_sections` in the supervisor graph. It checks `len(state["completed_sections"]) == len(state["sections_list"])`. On mismatch, it injects a visible placeholder section (e.g., `content="[Section omitted: research did not converge]"`) for each missing entry before proceeding to intro/conclusion.
- **Option B — Force Section call on researcher exit:** Modify `research_agent_tools` to detect when the researcher is exiting without having called `Section` and inject a failure-mode `Section` object with a `research_failed=True` flag. The supervisor can then decide whether to retry or surface the failure.
- **Option C — Supervisor retry on count mismatch:** Rather than injecting a placeholder, route back to re-dispatch the missing section(s) to a fresh researcher subagent (bounded by a retry counter).

Option A is the fastest, lowest-risk fix. Option C provides the best user outcome but requires retry orchestration.

### Suggested implementation (Option A)

```python
# multi_agent.py — add validation node

def validate_sections(state: ReportState) -> dict:
    """Ensure all planned sections were completed. Inject placeholders for any gaps."""
    sections_by_name = {s.name: s for s in state.get("completed_sections", [])}
    completed = []
    for section in state["sections"]:  # planned sections from Sections tool call
        if section.name in sections_by_name:
            completed.append(sections_by_name[section.name])
        else:
            # Inject a visible placeholder
            completed.append(Section(
                name=section.name,
                description=section.description,
                content=f"## {section.name}\n\n*This section could not be completed due to insufficient research results.*",
                research=False,
            ))
    return {"completed_sections": completed}

# Wire into supervisor graph after research_team, before intro/conclusion writing
```

## Related

- Finding: [No hard iteration cap on supervisor and researcher agent loops] — a turn cap on the researcher limits the window in which this silent exit can occur.
- The workflow graph (`graph.py`) avoids this problem by always terminating `write_section` with a completed section (either pass or max depth reached).
