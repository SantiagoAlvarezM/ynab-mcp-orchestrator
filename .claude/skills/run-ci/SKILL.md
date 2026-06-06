---
name: run-ci
description: Run the full local CI pipeline (lint → format check → type check → security scan → tests). Use before opening a PR or when you want to verify a branch is clean. Mirrors .github/workflows/ci.yml exactly.
---

Run these commands in order from the project root. Stop and report on the first failure.

1. `uv run ruff check .` — lint
2. `uv run ruff format --check .` — format check (does not modify files)
3. `uv run pyright` — type check
4. `uv run bandit -r src/` — security scan
5. `uv run pytest -v --tb=short` — tests

Report which steps passed and which failed. If any step fails, show the relevant output and suggest fixes before re-running.
