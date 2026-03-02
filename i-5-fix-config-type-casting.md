# I-5: Configuration.from_runnable_config does not cast env var strings to declared types

## Summary

**Context:** `Configuration.from_runnable_config()` reads config values from environment variables and LangGraph configurable, building a dict used to construct the Configuration dataclass.

**Bug:** `os.environ.get()` always returns strings, but the dataclass fields declare types like `int` (max_search_depth, number_of_queries) and `SearchAPI` (enum). The raw string values are passed directly to the constructor without casting.

**Actual vs. expected:** Setting `MAX_SEARCH_DEPTH=3` via env var → `configurable.max_search_depth` is `"3"` (str). When `graph.py` compares `state["search_iterations"] >= configurable.max_search_depth`, it raises `TypeError: '>=' not supported between instances of 'int' and 'str'`.

**Impact:** Deployments using environment variables for numeric config crash mid-workflow.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/configuration.py#L56-L72" />

```python
values: dict[str, Any] = {
    f.name: os.environ.get(f.name.upper(), configurable.get(f.name))
    for f in fields(cls)
    if f.init
}
return cls(**{k: v for k, v in values.items() if v})
# <-- BUG 🔴 No type casting — env vars are always strings
```

## Evidence

1. Set `MAX_SEARCH_DEPTH=3` in environment
2. `from_runnable_config()` reads `"3"` (string) from `os.environ.get("MAX_SEARCH_DEPTH")`
3. Dataclass accepts it (no validation in `__init__`)
4. `graph.py` line ~330: `state["search_iterations"] >= configurable.max_search_depth` → TypeError

### Affected fields (non-string types)

- `max_search_depth: int` — used in numeric comparison
- `number_of_queries: int` — used in numeric comparison
- `search_api: SearchAPI` — enum, string won't match enum members
- `planner_model_kwargs: Optional[Dict]` — expects dict, gets string

## Recommendation

Cast values using field type annotations:

```python
from dataclasses import fields
import json

@classmethod
def from_runnable_config(cls, config=None):
    configurable = (config["configurable"] if config and "configurable" in config else {})
    values = {}
    for f in fields(cls):
        if not f.init:
            continue
        raw = os.environ.get(f.name.upper(), configurable.get(f.name))
        if raw is None:
            continue
        # Cast to declared type
        if f.type == "int" or f.type is int:
            values[f.name] = int(raw)
        elif f.type == "bool" or f.type is bool:
            values[f.name] = raw if isinstance(raw, bool) else raw.lower() in ("true", "1")
        elif hasattr(f.type, "__members__"):  # Enum
            values[f.name] = f.type(raw) if isinstance(raw, str) else raw
        elif "Dict" in str(f.type) and isinstance(raw, str):
            values[f.name] = json.loads(raw)
        else:
            values[f.name] = raw
    return cls(**values)
```
