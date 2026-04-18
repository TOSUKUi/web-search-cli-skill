# web-search-cli

CLI and Codex skill replacement for the `hermes-web-search-plus` tool.

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

The installed CLI is provided by the `web-search-plus` console script in `pyproject.toml`.

If `web-search-plus` is not found after installation, the pip scripts directory is not on `PATH`. Add that scripts directory to `PATH`, then rerun the same `web-search-plus ...` command.

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

At least one provider credential or SearXNG instance is required for live search.

## Configuration

The CLI reads:

- `.env` in the repository root
- `config.json` in the repository root
- environment variables

Search result cache is stored in `~/.cache/web-search-cli` by default. Set `WSP_CACHE_DIR` to override it.

Common variables:

```bash
SERPER_API_KEY=
TAVILY_API_KEY=
EXA_API_KEY=
QUERIT_API_KEY=
PERPLEXITY_API_KEY=
KILOCODE_API_KEY=
YOU_API_KEY=
SEARXNG_INSTANCE_URL=
```

## Skill

The Codex skill is in `skills/web-search-plus-cli/SKILL.md`. It instructs Codex to use this CLI when current web evidence is needed from the local workspace.

## Validation

Non-network checks:

```bash
web-search-plus --help
web-search-plus --cache-stats --compact
web-search-plus --explain-routing --query "alternatives to Notion" --compact
```
