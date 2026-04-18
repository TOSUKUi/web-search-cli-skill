# web-search-cli

CLI and Codex skill replacement for the `hermes-web-search-plus` tool.

The project goal is functional replacement of the search tool, not replacement of the Hermes plugin host. The CLI keeps the same search engine behavior: multi-provider search, auto-routing, provider fallback/cooldown, cache, domain and recency filters, Exa deep modes, and JSON output.

## Quick Start

```bash
cp .env.example .env
python3 -m web_search_cli.search --query "OpenAI news today" --provider auto --max-results 5
```

For an installed command:

```bash
python3 -m pip install -e .
web-search-plus --query "LLM scaling laws research" --provider auto --max-results 5
```

Without installation:

```bash
./bin/web-search-plus --query "test query" --provider auto --max-results 5 --compact
```

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
python3 -m web_search_cli.search --help
python3 -m web_search_cli.search --cache-stats --compact
python3 -m web_search_cli.search --explain-routing --query "alternatives to Notion" --compact
```
