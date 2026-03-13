# I-2: Environment config values not type-coerced, breaking typed comparisons at runtime

## Summary

**Context:** `Configuration.from_runnable_config()` builds the runtime config dataclass by reading from `os.environ` with fallback to LangGraph `configurable` dict.

**Bug:** Environment variables are always strings, but the code passes them directly to the dataclass constructor without converting to the declared field types (`int`, `Optional[Dict]`, etc.).

**Actual vs. expected:** `MAX_SEARCH_DEPTH=2` stays as `"2"` (str) instead of `2` (int). `SEARCH_API_CONFIG={"max_results": 10}` stays as a raw string instead of a parsed dict.

**Impact:** Runtime TypeError/AttributeError mid-run after user has already approved a plan and paid for prior API calls.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/configuration.py#L56-L69" />

```python
values: dict[str, Any] = {
    f.name: os.environ.get(f.name.upper(), configurable.get(f.name))
    for f in fields(cls)
    if f.init
}
return cls(**{k: v for k, v in values.items() if v})
# <-- BUG 🔴 os.environ.get() always returns str, no coercion to field.type
```

Downstream typed usage:

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L330" />

```python
if feedback.grade == "pass" or state["search_iterations"] >= configurable.max_search_depth:
# <-- BUG 🔴 int >= str raises TypeError in Python 3
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L67" />

```python
return {k: v for k, v in search_api_config.items() if k in accepted_params}
# <-- BUG 🔴 .items() on a string raises AttributeError
```

## Evidence

### Example

1. Set `MAX_SEARCH_DEPTH=2` in `.env`
2. Start a research run, approve the plan
3. First section reaches grading at `graph.py:330`
4. `state["search_iterations"]` is `1` (int), `configurable.max_search_depth` is `"2"` (str)
5. `1 >= "2"` raises `TypeError: '>=' not supported between instances of 'int' and 'str'`
6. Run fails — user loses all prior API spend

## Impact

- **Reliability:** Any env-based deployment (the documented approach) can hit runtime crashes during research
- **User experience:** Failures happen mid-run after plan approval, wasting user time and API costs

## Recommendation

Add a `_coerce_value` helper in `from_runnable_config()` that inspects `field.type` and converts:

- `int` fields: `int(value)`
- `float` fields: `float(value)`
- `Optional[Dict[...]]` fields: `json.loads(value)` if string
- `str` fields: pass through

### Suggested implementation

```python
import json
from typing import get_type_hints, get_origin, get_args, Union

@classmethod
def from_runnable_config(cls, config=None):
    configurable = (config["configurable"] if config and "configurable" in config else {})
    hints = get_type_hints(cls)
    values = {}
    for f in fields(cls):
        if not f.init:
            continue
        raw = os.environ.get(f.name.upper(), configurable.get(f.name))
        if raw is not None:
            values[f.name] = cls._coerce_env_value(raw, hints.get(f.name))
    return cls(**values)

@staticmethod
def _coerce_env_value(value, type_hint):
    """Coerce a string env value to the declared field type."""
    if not isinstance(value, str):
        return value
    # Unwrap Optional[X] -> X
    origin = get_origin(type_hint)
    if origin is Union:
        args = [a for a in get_args(type_hint) if a is not type(None)]
        if args:
            type_hint = args[0]
            origin = get_origin(type_hint)
    if type_hint is int:
        return int(value)
    if type_hint is float:
        return float(value)
    if origin is dict or type_hint is dict:
        return json.loads(value)
    return value
```

## Related

The `.env.example` documents setting these variables, confirming env-based config is the intended deployment path.
