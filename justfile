set shell := ["sh", "-cu"]

default:
    @just --list

test:
    uv run --extra dev python -m unittest discover -s tests -v

lint:
    uv run --extra dev ruff check .

format:
    uv run --extra dev ruff format .

format-check:
    uv run --extra dev ruff format --check .

typecheck:
    uv run --extra dev pyright

check: lint format-check typecheck test
