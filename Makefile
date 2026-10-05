.PHONY: lint format typecheck test audit check sync

# Shared quality gate, matching the sibling projects. `check` runs every
# stage in sequence and stops at the first failure.
#
# `sync` installs the library in editable mode into ./.venv. From a clone:
#     uv venv && uv pip install -e ".[ui]" && make check

sync:
	uv venv
	uv pip install -e ".[ui]"
	uv pip install pytest pytest-cov mypy ruff vulture deptry detect-secrets \
		pip-audit setuptools

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .

typecheck:
	mypy src tests

test:
	pytest

audit:
	vulture src tests
	deptry .
	pip-audit

check: lint typecheck test audit