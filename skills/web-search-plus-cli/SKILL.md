---
name: web-search-plus-cli
description: Use the local web-search-plus CLI when Codex needs current web search results, provider auto-routing, domain or recency filters, Exa deep search, or a CLI replacement for the hermes-web-search-plus tool.
---

# Web Search Plus CLI

Use this skill when current web evidence is needed and the local repository CLI should be used instead of a hosted search connector or Hermes plugin.

## Goal

Provide `hermes-web-search-plus` search-tool functionality through a CLI plus this skill. The plugin host is out of scope.

## Runtime Modes

Choose exactly one of these modes for each invocation:

### Standalone mode (default)

The CLI performs the search locally. Provider credentials and `config.json`/`.env` are read from the local machine. Do not use `--serve` or `--satellite`.

```bash
web-search-plus --provider auto --query "..." --compact
```

This is the normal mode and remains the fallback when no satellite URL is configured. A repository `.env` is optional: provider credentials can be supplied directly as process environment variables, for example `EXA_API_KEY=your-exa-key web-search-plus --provider exa --query "..." --compact`. Process environment variables take precedence over values from `.env`.

### Server mode (central)

`--serve` starts the central HTTP search server. The server reads the config and provider credentials on its own host, then executes search requests received from satellites.

```bash
web-search-plus --serve \
  --config /srv/web-search/config.json \
  --server-host 127.0.0.1 --server-port 8765
```

`WSP_SERVER_TOKEN`/`--server-token` are optional. When set, satellites must send the matching `--satellite-token`; when unset, the server is unauthenticated and should stay on a trusted network. The built-in server is HTTP only; use TLS termination or an SSH tunnel for non-local traffic. `docker-compose.yml` is the supported containerized server setup.

### Satellite mode (client)

`--satellite URL` forwards the search request to a server instead of calling providers locally. The satellite does not need provider API keys; provider credentials are resolved by the central server.

```bash
web-search-plus --satellite http://127.0.0.1:8765 \
  --provider auto --query "..." --compact
```

The satellite forwards search options but cannot override central config or credential-bearing provider endpoints. `--serve` takes precedence if both controls are supplied, so do not combine the modes. `WSP_SATELLITE_URL` can select satellite mode without adding the flag.

## Command

Use the installed CLI after `pip install .`:

```bash
web-search-plus --query "<query>" --provider auto --max-results 5 --compact
```

If `web-search-plus` is not found after installation, the pip scripts directory is not on `PATH`. Do not switch interfaces unless the user asks; fix `PATH` and keep using the CLI.

## Provider Selection

- Prefer `--provider auto` unless the user requests a specific provider.
- Use `--provider serper` for Google-like facts, news, shopping, local, weather, places, images, videos, or shopping search.
- Use `--provider tavily` for research and analysis.
- Use `--provider exa` for semantic discovery, similar sites, alternatives, GitHub projects, papers, and deep modes.
- Use `--provider querit` for multilingual or metadata-rich real-time search.
- Use `--provider perplexity` for synthesized direct answers when configured.
- Use `--provider you` for LLM-ready snippets and current overview queries when configured.
- Use `--provider searxng` for a configured self-hosted/private metasearch instance.
- Use `--provider google_cse` for a configured Programmable Search Engine (`GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_ID`).
- Use `--provider serpapi` or `--provider scraperapi` for normalized SERP-scraping APIs.
- Use `--provider brightdata` for Bright Data’s direct SERP REST API; configure `BRIGHTDATA_API_KEY` and `BRIGHTDATA_SERP_ZONE`.

See `docs/providers.md` for the free-tier/monthly-quota catalog and official links.

## Common Options

- `--time-range day|week|month|year` for recency filters.
- `--include-domains example.com arxiv.org` to whitelist domains.
- `--exclude-domains reddit.com pinterest.com` to block domains.
- `--exa-depth normal|deep|deep-reasoning` for Exa depth.
- `--explain-routing` to debug provider choice without performing a provider search.
- `--cache-stats`, `--clear-cache`, and `--no-cache` for cache control.

## Environment

Live searches require at least one configured provider:

- `SERPER_API_KEY`
- `TAVILY_API_KEY`
- `EXA_API_KEY`
- `QUERIT_API_KEY`
- `PERPLEXITY_API_KEY` or `KILOCODE_API_KEY`
- `YOU_API_KEY`
- `GOOGLE_CSE_API_KEY` and `GOOGLE_CSE_ID`
- `SERPAPI_API_KEY`
- `SCRAPERAPI_API_KEY`
- `BRIGHTDATA_API_KEY` and `BRIGHTDATA_SERP_ZONE`
- `SEARXNG_INSTANCE_URL`

The CLI reads `.env`, `config.json` (or `--config PATH`), and the process environment from the repository root. `.env` is optional in standalone mode; use `export NAME=value` or prefix a command with `NAME=value` when supplying credentials directly. Process environment variables take precedence over `.env`. Multiple keys for one provider can be comma-separated in its environment variable, for example `SERPER_API_KEY=key-1,key-2`; keys are tried in order. A JSON array is also accepted for `api_key` in `config.json`.

For Docker-based server deployment, use `docker-compose.yml`; it mounts `config.json` read-only and persists the cache in a named volume. See [Runtime Modes](#runtime-modes) for the standalone, server, and satellite contracts.

## Output Handling

The CLI emits JSON. When answering the user:

1. Parse `results`, `answer`, `provider`, `routing`, `cached`, and `metadata`.
2. Cite URLs from `results[*].url`.
3. Mention provider fallback only when it affects confidence or explains missing results.
4. If all providers fail, summarize `provider_errors` and ask for credentials or a reachable SearXNG instance.

For exact flag mapping and output examples, read only the needed reference:

- `references/cli-contract.md` for Hermes tool parameter to CLI flag mapping.
- `references/env.md` for credential and config precedence.
- `references/output-schema.md` for success and error JSON shapes.

## Validation

Before relying on live provider calls, verify the CLI shape:

```bash
web-search-plus --help
web-search-plus --cache-stats --compact
web-search-plus --explain-routing --query "alternatives to Notion" --compact
```
