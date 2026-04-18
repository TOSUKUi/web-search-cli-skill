# Output Schema

The CLI emits JSON. Use `--compact` when another program or agent will parse the output.

## Success Shape

Typical fields:

```json
{
  "provider": "serper",
  "query": "example query",
  "results": [
    {
      "title": "Result title",
      "url": "https://example.com",
      "snippet": "Short excerpt"
    }
  ],
  "routing": {
    "auto_routed": true,
    "provider": "serper",
    "confidence": 0.8,
    "confidence_level": "high"
  },
  "cached": false,
  "deduplicated": false,
  "metadata": {
    "dedup_count": 0
  }
}
```

Provider-specific fields such as `answer`, `images`, `metadata`, or extracted text may appear.

## Failure Shape

All-provider failures are emitted as JSON on stderr with exit code 1:

```json
{
  "error": "All providers failed",
  "provider": "auto-selected-provider",
  "query": "example query",
  "routing": {},
  "provider_errors": [],
  "cooldown_skips": []
}
```

Credential errors identify the missing provider key or SearXNG URL.
