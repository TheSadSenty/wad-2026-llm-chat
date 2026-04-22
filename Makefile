SHELL := /usr/bin/env bash
UV ?= uv

.PHONY: lint
lint:
	$(UV) run ruff check --exit-non-zero-on-fix
	$(UV) run ruff format --check --diff
	$(UV) run flake8 .
	$(UV) run mypy .

.PHONY: unit
unit:
	$(UV) run pytest

.PHONY: unit_cov
unit_cov:
	$(UV) run pytest --cov --cov-branch

.PHONY: test
test: lint unit
