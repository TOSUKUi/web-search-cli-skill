# CLI Contract

## Hermes Tool Parameter Mapping

The CLI replaces the `web_search_plus` tool surface:

- `query` -> `--query`
- `provider` -> `--provider auto|serper|tavily|exa|querit|perplexity|you|searxng|google_cse|serpapi|scraperapi|brightdata`
- `count` -> `--max-results`
- `depth` -> `--exa-depth normal|deep|deep-reasoning`
- `time_range` -> `--time-range day|week|month|year`
- `include_domains` -> `--include-domains ...`
- `exclude_domains` -> `--exclude-domains ...`

## Required Parity

The CLI should preserve:

- Eleven providers: Serper, Tavily, Querit, Exa, Perplexity, You.com, SearXNG, Google CSE, SerpApi, ScraperAPI, Bright Data.
- Auto-routing with routing transparency.
- Exa `normal`, `deep`, `deep-reasoning`, and `--similar-url`.
- Provider fallback, retry, cooldown, and deduplication.
- Cache TTL, stats, clear, and bypass commands.
- JSON stdout as the canonical success contract.

## Useful Invocations

```bash
web-search-plus --query "..." --provider auto --max-results 5 --compact
web-search-plus --query "..." --provider exa --exa-depth deep --compact
web-search-plus --query "..." --time-range week --include-domains arxiv.org github.com --compact
web-search-plus --provider exa --similar-url "https://example.com" --compact
web-search-plus --explain-routing --query "alternatives to Notion" --compact
web-search-plus --cache-stats --compact
web-search-plus --clear-cache --compact
web-search-plus --satellite http://127.0.0.1:8765 --query "..." --compact
```
