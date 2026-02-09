# I-3: Add checkpointing to workflow graph

## Summary

**Context:** The Deep Research Reports workflow runs for several minutes, processing 5+ sections in parallel with 20-30+ paid API calls (search + LLM).

**Bug:** `builder.compile()` is called without a checkpointer in both `graph.py` and `multi_agent.py`. All intermediate state (completed sections, search results, queries) lives only in memory.

**Impact:** Any failure — transient API error, process restart, OOM — forces a complete restart of the entire pipeline. All paid API calls and completed sections are lost.

## Where

```python
# graph.py L485
graph = builder.compile()
# No checkpointer — all state is in-memory only

# multi_agent.py L331
graph = supervisor_builder.compile()
# Same — no checkpointer
```

LangGraph natively supports checkpointing via `builder.compile(checkpointer=...)`.

## Evidence

- `rg "checkpointer|MemorySaver|SqliteSaver" --type py` returns zero matches
- Neither graph compilation passes a checkpointer argument
- No persistence backend imported or configured

## Impact

- A failure at section 4/5 wastes all prior work (search API calls, LLM calls for sections 1-3)
- The human-in-the-loop plan approval step requires re-approval on restart
- No ability to inspect intermediate state for debugging
- Cost scales linearly with retries since nothing is preserved

## Recommendation

Add a LangGraph checkpointer to `builder.compile()`:

```python
# Option A: In-memory (development/testing)
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# Option B: SQLite (lightweight production)
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
graph = builder.compile(checkpointer=checkpointer)

# Option C: PostgreSQL (production at scale)
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string(os.environ["DATABASE_URL"])
graph = builder.compile(checkpointer=checkpointer)
```

**Note:** This is a ~5-line change per graph. LangGraph handles all persistence automatically once a checkpointer is configured. The workflow already uses `interrupt()` for human feedback, which benefits from checkpointing for proper resumption.

**Decision needed:** Which persistence backend to use (memory vs SQLite vs Postgres) depends on deployment context.
