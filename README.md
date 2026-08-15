# web-search-cli

CLI and Codex skill replacement for the `hermes-web-search-plus` tool.

日本語版: [README.ja.md](README.ja.md)

The project goal is functional replacement of the search tool, not replacement of the Hermes plugin host. The CLI keeps the same search engine behavior: multi-provider search, auto-routing, provider fallback/cooldown, cache, domain and recency filters, Exa deep modes, and JSON output.

## Quick Start

```bash
cp .env.example .env
pip install .
web-search-plus --query "OpenAI news today" --provider auto --max-results 5 --compact
```

For editable development:

```bash
pip install -e .
web-search-plus --query "LLM scaling laws research" --provider auto --max-results 5
```

To install the latest version directly from GitHub without a checkout:

```bash
pip install git+https://github.com/TOSUKUi/web-search-cli-skill
```

When installing without a checkout, provide credentials through process environment variables or an explicit `--config PATH`; the repository `.env.example` is available in the GitHub repository.

The installed CLI is provided by the `web-search-plus` console script in `pyproject.toml`.

If `web-search-plus` is not found after installation, the pip scripts directory is not on `PATH`. Add that scripts directory to `PATH`, then rerun the same `web-search-plus ...` command.

## Quota dashboard (Web UI)

Check which provider API keys are configured and how much quota remains in a browser:

```bash
python -m web_search_cli.webui --port 8901   # then open http://127.0.0.1:8901/
```

`--open` opens the dashboard in the default browser. `WSP_WEBUI_PORT` and `WSP_WEBUI_HOST` set the defaults.

The page reads credentials through the same config/env code path as the CLI and queries each provider's official usage endpoint (read-only; no searches are consumed):

| Provider | Remaining-quota API |
| --- | --- |
| Tavily | `GET /usage` — plan credits used/limit |
| SerpApi | `GET /account.json` — searches left, monthly reset |
| ScraperAPI | `GET /account` — credits left, billing reset |
| Serper, Exa, Querit, You.com, Perplexity, Google CSE, Bright Data, SearXNG | No public usage API — the card shows configured/not configured with a dashboard link |

Credential values are never exposed by the page or its endpoints; only presence and counts.

### Usage logging

Every successful CLI search appends one record to `~/.cache/web-search-cli/usage.jsonl` (append-only, best-effort, never fails a search). The dashboard shows the aggregated log: search counts per provider, last use, and — for Exa — accumulated cost from the `costDollars` field the API returns in each response body (free tier is ~$10/month of credits).

Response headers that look like quota indicators (`x-remaining`, `x-ratelimit-*`, `x-quota-*`, …) are captured automatically on every provider response and logged when present; none of the current providers send them, so the log's header column stays empty today. If a provider adds such headers later, they appear without code changes.

## Docker Compose central server

The included `docker-compose.yml` starts the central server with the API keys and config kept outside the image:

```bash
cp .env.example .env
cp config.example.json config.json
# Optionally set WSP_SERVER_TOKEN; add provider credentials in .env.
docker compose up -d --build
docker compose ps
docker compose logs -f web-search-central
```

The server listens on `http://127.0.0.1:8765` by default. Use `WSP_PUBLISHED_PORT` to change the host port. From a host-installed CLI, connect as a satellite:

```bash
web-search-plus --satellite http://127.0.0.1:8765 \
  --query "latest AI news" --compact
```

If `WSP_SERVER_TOKEN` is set on the server, add `--satellite-token "<the token value>"`.

`config.json` is mounted read-only and the cache uses a named Docker volume. Do not commit `.env` or `config.json`.

## Providers

Supported providers match the reference tool:

- `auto`
- `serper`
- `tavily`
- `querit`
- `exa`
- `perplexity`
- `you`
- `searxng`
- `google_cse`
- `serpapi`
- `scraperapi`
- `brightdata`

The free-tier and monthly-quota comparison is in [docs/providers.md](docs/providers.md).
Bright Data requires both `BRIGHTDATA_API_KEY` and a SERP zone in `BRIGHTDATA_SERP_ZONE` (or `brightdata.zone` in `config.json`). The zone must return parsed JSON; the adapter requests `brd_json=json` through Bright Data’s direct REST endpoint.

At least one provider credential or SearXNG instance is required for live search.

## Configuration

The CLI reads:

- `.env` in the repository root
- `config.json` in the repository root (override with `--config`)
- environment variables

A `.env` file is optional in standalone mode. You can set provider credentials directly in the process environment instead:

```bash
EXA_API_KEY=your-exa-key web-search-plus --provider exa --query "latest AI news" --compact
```

Use `export NAME=value` when the variables should apply to subsequent commands. If the same variable exists in both places, the process environment takes precedence over `.env`. In server mode, a `.env` beside the file passed to `--config` is also loaded. Search result cache is stored in `~/.cache/web-search-cli` by default. Set `WSP_CACHE_DIR` to override it.

### Multiple API keys

Provide multiple keys for one provider as a comma-separated environment variable. Keys are tried from left to right; a failed key is followed by the next one.

```bash
SERPER_API_KEY=serper-key-1,serper-key-2
TAVILY_API_KEY=tavily-key-1,tavily-key-2
```

In `config.json`, use either a comma-separated string or an array:

```json
{
  "serper": {
    "api_key": ["serper-key-1", "serper-key-2"]
  }
}
```

Existing single `PROVIDER_API_KEY` settings remain supported. If an API key contains a comma, use the JSON array form.

### Optional satellite mode

Run one central server with the provider credentials/config, then point satellite CLIs at it. Local mode remains the default:

```bash
web-search-plus --serve --config /srv/web-search/config.json --server-host 127.0.0.1 --server-port 8765
web-search-plus --satellite http://127.0.0.1:8765 --provider auto --query "latest AI news" --compact
```

The server accepts `/search` and `/health` requests. `WSP_SERVER_TOKEN` and `--satellite-token` are optional; set them when bearer authentication is desired. Satellite mode forwards search flags only; API keys stay on the central server. `--server-host` and `--server-port` are the server flags. For non-local use, put it behind TLS or an SSH tunnel; the built-in server is HTTP only.

Common variables:

```bash
SERPER_API_KEY=
TAVILY_API_KEY=
EXA_API_KEY=
QUERIT_API_KEY=
PERPLEXITY_API_KEY=
KILOCODE_API_KEY=
YOU_API_KEY=
GOOGLE_CSE_API_KEY=
GOOGLE_CSE_ID=
SERPAPI_API_KEY=
SCRAPERAPI_API_KEY=
BRIGHTDATA_API_KEY=
BRIGHTDATA_SERP_ZONE=
SEARXNG_INSTANCE_URL=
SEARXNG_ALLOW_PRIVATE=0
```

If `SEARXNG_INSTANCE_URL` intentionally points to a private/internal host (for example, a LAN or Docker address), set `SEARXNG_ALLOW_PRIVATE=1`. Leave it at `0` for public instances; this option disables the private-network URL guard.

## Skill

The Codex skill is in `skills/web-search-plus-cli/SKILL.md`. It instructs Codex to use this CLI when current web evidence is needed from the local workspace.

## Validation

Non-network checks:

```bash
web-search-plus --help
web-search-plus --cache-stats --compact
web-search-plus --explain-routing --query "alternatives to Notion" --compact
```
