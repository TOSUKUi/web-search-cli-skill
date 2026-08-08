# Current State

## Project Snapshot

The repository is being bootstrapped as `web-search-cli`: a CLI plus Codex skill replacement for the `hermes-web-search-plus` search tool. The local reference implementation remains in `hermes-web-search-plus/`.

## Stable Decisions

- The goal is search-tool functionality parity, not Hermes plugin compatibility.
- The primary interface is the installed `web-search-plus` CLI binary with JSON output.
- The Codex integration is a skill that invokes the CLI from the repository root.
- The search engine is based on the reference `hermes-web-search-plus/search.py` behavior: multi-provider search, auto-routing, cache, provider cooldown/fallback, domain filters, recency filters, and Exa deep modes.

## Active Work

- Package the CLI for direct use through installed console script `web-search-plus`.
- Document the Codex skill contract in `skills/web-search-plus-cli/SKILL.md`.
- Validate non-network CLI paths before live provider testing.
- Expand provider choices with free-tier/monthly-quota candidates while preserving existing auto-routing behavior.

## Recent Accepted Changes

- Added root packaging, runner, environment/config examples, Codex skill, and project-state docs.
- Vendored the reference search engine into `web_search_cli/search.py` as the CLI core.
- Added `.gitignore` entries for generated Python/cache/config artifacts.
- Clarified that normal `pip install .` should expose the `web-search-plus` CLI, and user-facing docs should stay on CLI-only usage.
- Set the default search-result cache directory to `~/.cache/web-search-cli`, with `WSP_CACHE_DIR` override preserved.
- Added multiple provider API keys via comma-separated environment variables or JSON arrays, with ordered key fallback and legacy single-key compatibility.
- Added optional central server/satellite mode (`--serve` and `--satellite`); the central host owns credentials/config and exposes optionally authenticated search and health endpoints.
- Added a minimal Docker Compose deployment (`docker-compose.yml`) with a read-only central config mount, optional server token, non-root container user, and persistent cache volume.
- Added a Japanese user-facing README at `README.ja.md` and linked it from the English README.
- Added Google Custom Search JSON, SerpApi, ScraperAPI, and Bright Data adapters plus a broader free-tier catalog in `docs/providers.md`.

## Open Risks

- Live provider behavior requires API keys or a reachable SearXNG instance.
- Network-bound provider calls are not validated by non-network checks.
- Satellite mode has been exercised locally with the central HTTP server, but live provider execution through it still requires credentials.
- The reference project has no test suite; this repository now has focused non-network provider parsing/config tests.
- Four additional explicit/fallback adapters are implemented: Google Custom Search JSON, SerpApi, ScraperAPI, and Bright Data. See `docs/providers.md` for the broader candidate catalog and quota caveats.
