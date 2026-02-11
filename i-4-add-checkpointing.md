# I-4: No LangGraph checkpointing causes lost progress on mid-run failures

## Summary

**Context:** Both `graph.py` and `multi_agent.py` compile LangGraph StateGraphs that orchestrate multi-minute report generation workflows with 20-30+ API calls.

**Bug:** Neither graph is compiled with a checkpointer, so all intermediate state lives only in memory.

**Actual vs. expected:** When any step fails mid-run, the workflow should be resumable from the last successful node. Instead, it must restart from scratch.

**Impact:** A transient error on section 5 of 8 forces re-execution of sections 1–4, wasting minutes of time and the API costs for all completed work.

## Where

Main workflow — `graph.py` line 485:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L469-L485" />

```python
graph = builder.compile()
# <-- BUG 🔴 No checkpointer — all state lost on failure
```

Multi-agent variant — `multi_agent.py` line 331:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/multi_agent.py#L313-L331" />

```python
graph = builder.compile()
# <-- BUG 🔴 No checkpointer — all state lost on failure
```

## Evidence

- A typical report researches 5–8 sections with 2+ search queries and 2+ LLM calls per section
- Total: 20–30+ API calls over several minutes
- Search functions lack error handling (separate issue), making mid-run failures likely
- No `checkpointer` parameter in either `builder.compile()` call

## Impact

- **Wasted cost:** Re-executing completed sections wastes search and LLM API credits
- **Wasted time:** Multi-minute pipelines restart from scratch on any failure
- **Compounding risk:** Without error handling on search functions, failures are frequent — every failure triggers a full restart

## Recommendation

Add a LangGraph checkpointer to `builder.compile()` in both files. LangGraph handles state persistence automatically once a checkpointer is provided.

**Decision needed:**

- Option A: `MemorySaver` — Zero config, in-memory only. Good for development. State lost on process restart.
- Option B: `SqliteSaver` — Lightweight file-based persistence. Good for local/single-user. State survives process restart.
- Option C: `PostgresSaver` — Production-grade. Requires external database. Best for multi-user deployments.

### Suggested implementation (Option A — minimal)

```python
# graph.py
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)
```

```python
# multi_agent.py
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)
```

~5 lines changed per file. LangGraph handles all state serialization and restoration automatically.
