.DEFAULT_GOAL := help
.PHONY: help install lint typecheck test check hooks fetch-data

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

fetch-data: ## Download competition data into data/ (needs the Kaggle CLI)
	bash scripts/fetch_data.sh
