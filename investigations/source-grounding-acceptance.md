# Sections can pass without source-grounding checks

## Summary

**Context:** Open Deep Research writes section drafts from retrieved source text, grades each section, and publishes passing sections into the final report.

**Problem:** The runtime acceptance check verifies topical adequacy, but it does not verify that citations exist, cite retrieved URLs, or support the claims in the section.

**Impact:** Users can receive a polished report with unsupported claims or broken citations even though the section passed review.

**Recommendation:** Add a lightweight source-integrity gate before a section is added to completed sections.

## Evidence

- Linked issue: https://introspection.dev/issues/019e3a40-7975-7563-b0f8-507e90535a92
- `src/open_deep_research/prompts.py` asks the writer to ground every claim and list sources.
- `src/open_deep_research/graph.py` publishes a section when the grader returns `pass` or search depth is exhausted.
- The grader prompt asks whether the section addresses the topic and what follow-up queries are needed; it does not check citation-to-source integrity.

## Options

| Option | What changes | Pros | Cons |
| ------ | ------------ | ---- | ---- |
| A | Parse cited URLs from each section and compare them with URLs present in the section's retrieved source context before accepting the section. | Small, deterministic, catches missing or fabricated source URLs. | Does not prove every individual claim is supported. |
| B | Add a second structured grounding review that returns unsupported claim spans and required follow-up queries. | Stronger source-faithfulness control. | More model cost and another prompt surface to maintain. |
| C | Require the writer to emit a structured citation map while drafting the section. | Gives future controls better data. | Larger prompt/schema change and higher migration risk. |

## Recommended Plan

1. Start with Option A as the minimum acceptance gate.
2. Carry the retrieved source URLs alongside the source text for each section.
3. Before publishing a completed section, parse cited URLs and fail the section if there are no citations, citations not in retrieved URLs, or an empty source list.
4. Route failed source-integrity checks through targeted follow-up research while search depth remains; otherwise publish a clear partial-failure message instead of a clean section.
5. Consider Option B later if unsupported claims remain common after URL integrity is enforced.

## Acceptance Criteria

- [ ] Issue is linked to this PR.
- [ ] Section completion requires citation URLs to match retrieved source URLs.
- [ ] Sections with missing or invalid citations are not silently accepted as complete research.
- [ ] The failure path either retries with follow-up research or surfaces a clear partial-failure state.
