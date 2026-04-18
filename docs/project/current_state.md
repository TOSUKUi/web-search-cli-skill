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

## Recent Accepted Changes

- Added root packaging, runner, environment/config examples, Codex skill, and project-state docs.
- Vendored the reference search engine into `web_search_cli/search.py` as the CLI core.
- Added `.gitignore` entries for generated Python/cache/config artifacts.
- Clarified that normal `pip install .` should expose the `web-search-plus` CLI, and user-facing docs should stay on CLI-only usage.
- Set the default search-result cache directory to `~/.cache/web-search-cli`, with `WSP_CACHE_DIR` override preserved.

## Open Risks

- Live provider behavior requires API keys or a reachable SearXNG instance.
- Network-bound provider calls are not validated by non-network checks.
- The reference project has no test suite, so parity is currently structural and CLI-contract based.
