# I-3: Approving a plan with zero research sections dead-ends the graph

## Summary

**Context:** After human approval, `human_feedback()` dispatches `Send()` commands only for sections with `research=True`, which then flow through the research → grade → compile pipeline.

**Bug:** When the filtered list of research sections is empty, zero `Send()` commands are emitted. The graph has no fallback edge from `human_feedback` to `gather_completed_sections` or `compile_final_report`.

**Actual vs. expected:** The run silently dead-ends after approval instead of producing a report (even a minimal one) or notifying the user.

**Impact:** Users approve a plan and receive nothing — no report, no error.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L166-L173" />

```python
if isinstance(feedback, bool) and feedback is True:
    return Command(goto=[
        Send("build_section_with_web_research", {"topic": topic, "section": s, "search_iterations": 0}) 
        for s in sections 
        if s.research
    ])
    # <-- BUG 🔴 If no sections have research=True, goto=[] — graph has nowhere to go
```

Graph wiring confirms no fallback:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L477-L483" />

```python
builder.add_edge("build_section_with_web_research", "gather_completed_sections")
builder.add_conditional_edges("gather_completed_sections", initiate_final_section_writing, ["write_final_sections"])
builder.add_edge("write_final_sections", "compile_final_report")
# No edge from human_feedback -> gather_completed_sections
```

## Evidence

### Example

1. User requests a report on a topic
2. Planner generates sections with only intro/conclusion (all `research=False`)
3. User approves the plan
4. `human_feedback()` returns `Command(goto=[])` — empty send list
5. No downstream nodes fire
6. Run completes with no `final_report` in state

## Impact

- **User experience:** Silent failure — user waits indefinitely or sees an empty result after approving
- **Reliability:** Edge case triggered by planner output or user-edited plans

## Recommendation

Add a guard after filtering research sections:

```python
research_sections = [s for s in sections if s.research]
if not research_sections:
    # Option A: Route directly to final section writing with all sections as non-research
    return Command(
        update={"completed_sections": []},
        goto="gather_completed_sections"
    )
    # Option B: Return feedback telling the user at least one section needs research
    # return Command(goto="human_feedback", update={"feedback_on_report_plan": "..."})
```

**Decision needed:**
- Option A: Auto-route to compilation with available sections — produces a report without web research
- Option B: Reject the plan and ask user to mark at least one section for research — prevents low-quality output
