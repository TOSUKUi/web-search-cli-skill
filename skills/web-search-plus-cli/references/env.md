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
- Provider API key variables accept comma-separated values, for example `SERPER_API_KEY=key-1,key-2`; keys are tried from left to right.
- `WSP_SATELLITE_URL` and `WSP_SATELLITE_TOKEN` select the central server from a satellite CLI.
- `WSP_SERVER_TOKEN` protects the central server; `WSP_SERVER_HOST` and `WSP_SERVER_PORT` configure its bind address.
- `SEARXNG_ALLOW_PRIVATE=1` permits private/internal SearXNG hosts.

## Standalone without `.env`

A repository `.env` file is optional. Set credentials directly in the process environment:

```bash
EXA_API_KEY=your-exa-key web-search-plus --provider exa --query "latest AI news" --compact
```

Use `export NAME=value` for subsequent commands. Process environment variables take precedence over values from `.env`.

## Multiple API keys

Use a comma-separated environment variable:

```bash
SERPER_API_KEY=key-1,key-2
```

Or use a JSON array in provider config:

```json
{"serper": {"api_key": ["key-1", "key-2"]}}
```

Keys are tried in order. Existing single-key provider config and environment variables remain supported. If a key contains a comma, use the JSON array form. Never commit real keys to config files.

## Precedence

Provider settings are resolved from:

1. `config.json` (or the selected `--config` file)
2. process environment
3. the repository/config-directory `.env` file, which only fills variables absent from the process environment

Use `.env.example` and `config.example.json` as templates. A central server also loads a `.env` beside its central config file.
