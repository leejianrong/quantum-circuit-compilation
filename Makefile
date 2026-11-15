.DEFAULT_GOAL := help
.PHONY: help install lint typecheck test check hooks fetch-data docs docs-serve dashboard plots-readme report learn-figures log log-check log-prs

help: ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install: ## Sync the uv environment
	uv sync

lint: ## ruff check + format check
	uv run ruff check . && uv run ruff format --check .

typecheck: ## mypy
	uv run mypy

test: ## Fast no-infra tests (no kickmix, no competition data)
	uv run pytest

check: lint typecheck test ## What the pre-push hook and CI run

hooks: ## Install the pre-push hook
	git config core.hooksPath .githooks

learn-figures: ## Redraw docs/img/learn/*.svg (learning-track figures) from code and analysis/numbers/learn.json; needs the plots extra
	uv run --extra plots python -m analysis.learn_figures docs/img/learn

log: ## Lint docs/log/entries and rewrite the generated log and results pages
	uv run python -m bench.logbook

log-prs: ## Re-snapshot the pull requests with gh (analysis/numbers/prs.json) and rebuild the log pages
	uv run python -m bench.logbook --refresh-prs

log-check: ## Lint the log entries and fail if a generated page is stale (also run by the tests)
	uv run python -m bench.logbook --check

docs: ## Build the learning site into site/ (snippets are run by `make test`)
	uv run zensical build --clean --strict

docs-serve: ## Serve the learning site locally with live reload
	uv run zensical serve

fetch-data: ## Download competition data into data/ (needs the Kaggle CLI)
	bash scripts/fetch_data.sh

dashboard: ## Run the local dashboard (needs `uv sync --extra dashboard`); prints a URL on the first free port
	uv run python -m dashboard

plots-readme: ## Redraw docs/img/*.png (plots and dashboard screenshots) from the live ledger; light, verifies nothing
	uv run --extra plots --extra dashboard --extra shots python scripts/plots_readme.py

report: ## Analysis figures (docs/img/analysis) and the PDF report (out/reports) from analysis/data/*.json; needs the plots extra
	uv run --extra plots python -m analysis.dqi_figures docs/img/analysis
	uv run --extra plots python -m analysis.report out/reports/qcc-analysis.pdf
