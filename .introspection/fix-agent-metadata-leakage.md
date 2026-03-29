# Fix: Agent leaks hidden project context in generic conversational responses

## Summary

**Context:** The Introspection Agent is injected with project-scoping context at conversation start — including the linked repository slug (`rolandgvc/open_deep_research`) and system name (`Deep Research`). This is intended to make the agent workspace-aware for task execution.

**Bug:** The system prompt does not restrict when this metadata may be surfaced. The agent volunteers the repo slug and system name in response to generic queries (e.g. "what can you do") where workspace identity is irrelevant.

**Actual vs. expected:**
- **Actual:** Reply to "what can you do" ends with "Your linked repo is `rolandgvc/open_deep_research` and your system is **Deep Research**."
- **Expected:** Generic capability answers contain no workspace identifiers unless the user explicitly requests them.

**Impact:** Users receive unsolicited internal workspace identifiers on routine turns. Sensitive repo names or system identifiers may appear in shared screens, support sessions, or logs.

## Where

The issue is in the Introspection Agent's system prompt — specifically the section that injects project context into the preloaded prompt block (confirmed by `cache_read_input_tokens: 7958` with no tool calls in the trace).

The relevant template/configuration is in the agent platform, not in this repository. The fix belongs to whoever owns the agent's system prompt or context injection layer.

## Evidence

### Example

Conversation `019d35b9-c21b-73dc-a936-0d204f131b4d`, turn 3:

1. User sends: "what can you do"
2. No tool calls made, no errors raised
3. Assistant reply ends: *"Your linked repo is `rolandgvc/open_deep_research` and your system is **Deep Research**."*

Span `aafab62c194ad500` contains the full LLM output. The cached context block (`cache_read_input_tokens: 7958`) is the source — the metadata was read from the pre-loaded system prompt and echoed verbatim.

### Root cause

The system prompt injects project metadata (repo, system name) unconditionally and does not instruct the agent to treat this information as silent operating context. The model defaults to mentioning it when composing a "helpful" capability overview.

## Impact

- **Trust / UX:** Users are surprised by workspace identifiers they didn't ask about, eroding confidence in the agent's judgment.
- **Privacy:** In team/shared environments, repo names and system identifiers could be visible in screen recordings, chat exports, or support tickets.
- **Consistency:** The agent behaves differently for identical generic prompts depending on which workspace is active.

## Recommendation

Update the system prompt to explicitly scope when project metadata may be surfaced.

**Decision needed:**

- **Option A (preferred) — Explicit suppression instruction:** Add a line to the context injection block, e.g.:
  > "Treat the linked repository and system name as silent operating context. Do not mention them in responses unless the user explicitly asks about your workspace or the task directly involves them."

- **Option B — Output filtering:** Add an application-layer post-processing step that detects and strips workspace identifiers from responses to generic/chit-chat turns before delivery. More robust but adds latency and complexity.

- **Option C — Separate context block with role tag:** Move project metadata to a `<context>` XML block with a `role="tool"` tag style and instruct the model that `<context>` blocks are never to be quoted or paraphrased in user-visible output.

### Suggested implementation (Option A)

In the system prompt template, after the project context injection:

```
# Workspace Context (silent — do not surface unless asked)
- Linked repository: rolandgvc/open_deep_research
- System: Deep Research

Do not volunteer the above identifiers in responses. Use them only when
the user asks about their workspace or the task requires referencing them.
```

### Regression tests to add

Cover these prompts and assert no workspace metadata appears in replies:
- "what can you do"
- "hi" / "hello"
- "help"
- "who are you"
- "what is this"

## Related

- Issue #4 in this project (Introspection issue `019d3b7f-af08-70ca-aaae-93d4e9ad67ac`)
- Feedback `019d36aa-80b4-7158-b758-d85a8902b2b6`
