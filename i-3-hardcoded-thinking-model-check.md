# I-3: Hardcoded model name check silently disables extended thinking

## Summary

**Context:** The workflow uses extended thinking (16K token budget) for the two most quality-sensitive steps: report planning (`generate_report_plan`) and section grading (`write_section`). This enables deeper reasoning for structuring reports and evaluating section quality.

**Bug:** Extended thinking is gated behind an exact string comparison: `if planner_model == "claude-3-7-sonnet-latest"`. This check appears in two places with duplicated initialization logic.

**Actual vs. expected:** When the model name doesn't match exactly, the `else` branch initializes the model without any `thinking` parameters — silently degrading output quality with no error or warning. Expected: thinking should be configurable independently of the model name.

**Impact:** Planning and grading quality silently degrades when the model name doesn't match the hardcoded string, which happens when Anthropic updates model aliases, users add provider prefixes, or a different thinking-capable model is configured.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L108-L119" />

```python
if planner_model == "claude-3-7-sonnet-latest":
    # <-- BUG 🔴 Exact string match — breaks on alias changes, prefixes, other thinking models
    planner_llm = init_chat_model(model=planner_model, 
                                  model_provider=planner_provider, 
                                  max_tokens=20_000, 
                                  thinking={"type": "enabled", "budget_tokens": 16_000})
else:
    # Silently falls through here with degraded quality — no warning
    planner_llm = init_chat_model(model=planner_model, 
                                  model_provider=planner_provider,
                                  model_kwargs=planner_model_kwargs)
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/graph.py#L316-L327" />

Same pattern duplicated for section grading.

## Evidence

### Scenario 1: Model alias update

1. Anthropic releases a new snapshot and updates the `claude-3-7-sonnet-latest` alias to point to `claude-3-7-sonnet-20260115`
2. User configures `planner_model: "claude-3-7-sonnet-20260115"` (or Anthropic changes what `latest` resolves to in their API)
3. The exact string check fails
4. Planning runs without extended thinking — report structure quality degrades
5. No error, no warning — user doesn't know why reports are worse

### Scenario 2: Future thinking-capable model

1. User upgrades to `claude-4-sonnet` (thinking-capable)
2. The check fails — no thinking budget allocated
3. The model can think but isn't asked to, producing shallower plans

### Code duplication

The identical model initialization logic appears in two places (lines 108-119 and 316-327). A fix in one place must be replicated in the other — a maintenance hazard.

## Impact

- **Quality:** Planning and grading are the most critical steps in the workflow. Without extended thinking, the planner produces less structured reports and the grader provides less thorough feedback.
- **Maintainability:** The check must be updated every time Anthropic releases a new thinking-capable model. Duplicated in two places doubles the chance of missing one.
- **User experience:** Silent degradation — no error tells the user their configuration is suboptimal.

## Recommendation

Add `enable_thinking` and `thinking_budget` to `Configuration` and extract a helper function.

### Suggested implementation

```python
# configuration.py — add fields
@dataclass(kw_only=True)
class Configuration:
    # ... existing fields ...
    enable_thinking: bool = True  # Enable extended thinking for planning/grading
    thinking_budget: int = 16_000  # Token budget for extended thinking

# graph.py — extract helper
def init_planner_llm(configurable: Configuration):
    """Initialize planner/grader model with optional thinking."""
    provider = get_config_value(configurable.planner_provider)
    model = get_config_value(configurable.planner_model)
    
    if configurable.enable_thinking:
        return init_chat_model(
            model=model,
            model_provider=provider,
            max_tokens=20_000,
            thinking={"type": "enabled", "budget_tokens": configurable.thinking_budget}
        )
    else:
        model_kwargs = get_config_value(configurable.planner_model_kwargs or {})
        return init_chat_model(
            model=model,
            model_provider=provider,
            model_kwargs=model_kwargs
        )

# Use in both generate_report_plan (line 108) and write_section (line 316)
planner_llm = init_planner_llm(configurable)
```

## Related

- The `writer_model` initialization does not have this problem — it uses `model_kwargs` consistently
- `configuration.py` already has `planner_model_kwargs` which could theoretically carry thinking params, but the hardcoded check bypasses it
