# Environment And Config

## Runtime

- Python 3.8+
- No required Python package dependencies for the current engine.

## Provider Configuration

Configure at least one provider for live search:

- `SERPER_API_KEY`
- `TAVILY_API_KEY`
- `EXA_API_KEY`
- `QUERIT_API_KEY`
- `PERPLEXITY_API_KEY`
- `KILOCODE_API_KEY`
- `YOU_API_KEY`
- `SEARXNG_INSTANCE_URL`

Optional:

- `WSP_CACHE_DIR` sets the cache directory.
- If `WSP_CACHE_DIR` is unset, the default cache directory is `~/.cache/web-search-cli`.
- `SEARXNG_ALLOW_PRIVATE=1` permits private/internal SearXNG hosts.

## Precedence

Provider settings are resolved from:

1. `config.json`
2. repo-root `.env`
3. process environment

Use `.env.example` and `config.example.json` as templates.
