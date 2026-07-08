# Makefile for Unix users (Windows users: use tasks.ps1 or tasks.py).
SRC := src app tests

.PHONY: setup run test lint format typecheck check

setup:
	uv sync

run:
	uv run streamlit run app/streamlit_app.py

test:
	uv run pytest -q

lint:
	uv run ruff check $(SRC)
	uv run ruff format --check $(SRC)

format:
	uv run ruff format $(SRC)
	uv run ruff check --fix $(SRC)

typecheck:
	uv run mypy src

check: lint typecheck test
