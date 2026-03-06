# I-14: Perplexity and Google search adapters lack HTTP timeouts

## Summary

**Context:** The Deep Research workflow supports multiple search backends (Tavily, Perplexity, Google scraping) configured via `SearchAPI` enum. The Perplexity and Google adapters make HTTP calls using Python `requests`.

**Bug:** Both `requests.post` (Perplexity) and `requests.get` (Google) omit the `timeout` parameter. Python `requests` blocks indefinitely by default.

**Actual vs. expected:** A slow or unresponsive upstream should fail with a timeout error after a reasonable period. Instead, the workflow thread hangs forever.

**Impact:** Users on Perplexity or Google backends can experience indefinitely stalled runs with no error message.

## Where

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L232-L236" />

```python
response = requests.post(
    "https://api.perplexity.ai/chat/completions",
    headers=headers,
    json=payload
)
# <-- BUG 🔴 No timeout parameter — blocks indefinitely if Perplexity is slow
```

<github_code url="https://github.com/rolandgvc/open_deep_research/blob/62c8ffc9c2525956fd43f69aba95027f8d7a1b89/src/open_deep_research/utils.py#L938-L955" />

```python
resp = requests.get(
    url="https://www.google.com/search",
    headers={...},
    params={...},
    cookies={...}
)
# <-- BUG 🔴 No timeout parameter — blocks indefinitely if Google is slow/blocked
```

## Evidence

Both calls use `requests` without `timeout`. Per Python docs: "You can tell Requests to stop waiting for a response after a given number of seconds with the timeout parameter. Nearly all production code should use this parameter in nearly all requests."

## Impact

- **Availability:** Workflow hangs indefinitely — no error, no retry, no timeout
- **UX:** User sees a stuck run with no feedback on what went wrong
- **Cascade:** In the Google scraping path, this is inside a while loop — a single hung request blocks the entire research section

## Recommendation

Add a `timeout` parameter to both calls. A shared constant keeps it consistent.

```python
# In utils.py or a constants module
SEARCH_HTTP_TIMEOUT_SECONDS = 30

# Perplexity call (line ~232)
response = requests.post(
    "https://api.perplexity.ai/chat/completions",
    headers=headers,
    json=payload,
    timeout=SEARCH_HTTP_TIMEOUT_SECONDS,
)

# Google call (line ~938)
resp = requests.get(
    url="https://www.google.com/search",
    headers={...},
    params={...},
    cookies={...},
    timeout=SEARCH_HTTP_TIMEOUT_SECONDS,
)
```

No decision needed — this is a straightforward fix. The only consideration is the timeout value; 30s is reasonable for external search APIs.

## Related

- Issue #4: Covers missing retry/timeout on LLM and Tavily calls — together these close the timeout gap across all backends
