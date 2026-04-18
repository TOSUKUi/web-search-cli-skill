# AGENTS.md

## Project Purpose

This repository provides a CLI and Codex skill replacement for the `hermes-web-search-plus` search tool. The target is tool-function parity for search behavior, not Hermes plugin compatibility.

## Source Of Truth Map

- `web_search_cli/search.py`: canonical CLI search engine.
- `skills/web-search-plus-cli/SKILL.md`: Codex-facing operating instructions for the CLI.
- `README.md`: user-facing setup and validation notes.
- `docs/project/current_state.md`: compressed project status.
- `docs/project/critical_path.md`: active dependency chain and blockers.
- `hermes-web-search-plus/`: local reference implementation only.

## Task Loop Rules

- Preserve CLI parity with the reference search tool unless a change is explicitly scoped.
- Keep plugin-host concerns out of the CLI replacement.
- Prefer repo evidence over chat history when updating durable docs.
- Mark unknowns instead of inventing roadmap, blockers, or credentials.

## Durable Artifacts

- CLI package: `web_search_cli/`
- Direct runner: `bin/web-search-plus`
- Codex skill: `skills/web-search-plus-cli/`
- Environment template: `.env.example`
- Configuration template: `config.example.json`

## Resume Order

1. Read `docs/project/current_state.md`.
2. Read `docs/project/critical_path.md`.
3. Check `README.md` for user-facing commands.
4. Inspect `web_search_cli/search.py` only when implementation detail is needed.

## Write-Back Rule

When the project goal, active dependency chain, or accepted CLI behavior changes, update the project docs in the same change set.
