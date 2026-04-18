---
name: web-search-plus-cli
description: Use the local web-search-plus CLI when Codex needs current web search results, provider auto-routing, domain or recency filters, Exa deep search, or a CLI replacement for the hermes-web-search-plus tool.
---

# Web Search Plus CLI

Use this skill when current web evidence is needed and the local repository CLI should be used instead of a hosted search connector or Hermes plugin.

## Goal

Provide `hermes-web-search-plus` search-tool functionality through a CLI plus this skill. The plugin host is out of scope.

## Command

From the repository root:

```bash
./bin/web-search-plus --query "<query>" --provider auto --max-results 5 --compact
```

Equivalent module invocation:

```bash
python3 -m web_search_cli.search --query "<query>" --provider auto --max-results 5 --compact
```

Fallback direct script invocation:

```bash
python3 web_search_cli/search.py --query "<query>" --provider auto --max-results 5 --compact
```

## Provider Selection

- Prefer `--provider auto` unless the user requests a specific provider.
- Use `--provider serper` for Google-like facts, news, shopping, local, weather, places, images, videos, or shopping search.
- Use `--provider tavily` for research and analysis.
- Use `--provider exa` for semantic discovery, similar sites, alternatives, GitHub projects, papers, and deep modes.
- Use `--provider querit` for multilingual or metadata-rich real-time search.
- Use `--provider perplexity` for synthesized direct answers when configured.
- Use `--provider you` for LLM-ready snippets and current overview queries when configured.
- Use `--provider searxng` for a configured self-hosted/private metasearch instance.

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
- `SEARXNG_INSTANCE_URL`

The CLI reads `.env`, `config.json`, and the process environment from the repository root.

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
./bin/web-search-plus --help
./bin/web-search-plus --cache-stats --compact
./bin/web-search-plus --explain-routing --query "alternatives to Notion" --compact
```
