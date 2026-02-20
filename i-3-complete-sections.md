# I-3: Supervisor finalizes report before all sections complete

## Summary

**Context:** The multi-agent supervisor coordinates multiple researcher agents and then assembles the final report with an introduction and conclusion.

**Bug:** The supervisor treats research as complete as soon as any completed section exists, without ensuring all planned sections have finished.

**Actual vs. expected:** The supervisor moves on to write the introduction/conclusion after the first section completes, rather than waiting for every section.

**Impact:** Final reports can be missing sections, with no explicit error.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L115-L196" />

```python
# multi_agent.py (supervisor_state_prompt)
if completed_sections:
    instructions = "Research is complete. Now write the introduction and conclusion."
    # <-- BUG 🔴 Does not wait for all sections to complete
```

## Evidence

### Example

1. Supervisor assigns 3 sections to researchers.
2. Researcher A returns its section first.
3. completed_sections becomes non-empty and the supervisor writes intro/conclusion.
4. Researchers B/C return later but their sections are not included in the final assembly.

### Inconsistency

- Planned sections list includes multiple items.
- Completion check only verifies that at least one section exists.

## Impact

- **Reliability:** Reports may be incomplete without warning.
- **User trust:** Missing sections reduce report quality and can omit key analysis.

## Recommendation

Track the expected number of sections and gate final assembly until all are present, or add a join node that aggregates all section outputs before completion.

### Suggested implementation

```python
expected_sections = len(sections_list)
if len(completed_sections) == expected_sections:
    # proceed to intro/conclusion
```

## Related

None.
