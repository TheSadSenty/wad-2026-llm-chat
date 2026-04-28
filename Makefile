SHELL := /usr/bin/env bash
UV ?= uv
APP_FOLDER := ./app/

.PHONY: ruff_formatter
ruff_formatter:
	$(UV) run ruff format

.PHONY: mypy
mypy:
	$(UV) run mypy $(APP_FOLDER)

.PHONY: ruff
ruff:
	$(UV) run ruff check --exit-non-zero-on-fix
	$(UV) run ruff format --check --diff

.PHONY: linters
linters: ruff mypy

.PHONY: unit
unit:
	$(UV) run pytest

.PHONY: unit_cov
unit_cov:
	$(UV) run pytest --cov --cov-branch
