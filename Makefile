# Creative Reformatting Engine
SHELL := /bin/bash
PY    := .venv/Scripts/python.exe          # on macOS/Linux: .venv/bin/python
UV    := uv

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

## ---------------------------------------------------------------- setup ----
venv: ## Create the virtualenv
	$(UV) venv .venv --python 3.12

install: venv ## Install backend (editable) + dev tooling
	$(UV) pip install --python $(PY) -e "backend[dev]"

install-aws: ## Add the AWS extras (boto3)
	$(UV) pip install --python $(PY) -e "backend[dev,aws]"

models: ## Pre-fetch the MediaPipe model bundles into data/models
	$(PY) -m cre.vision.models

frontend-install: ## Install frontend dependencies
	cd frontend && npm install --no-audit --no-fund

setup: install models frontend-install ## Full local setup

## ------------------------------------------------------------------ run ----
api: ## Run the API + in-process worker on :8000
	$(PY) -m uvicorn cre.main:app --reload --host 0.0.0.0 --port 8000

web: ## Run the frontend dev server on :5173
	cd frontend && npm run dev

## ------------------------------------------------------------------ cli ----
spec: ## Print the loaded platform spec sheet
	$(PY) -m cre.cli spec

process: ## Reformat a master: make process FILE=test_sample/input_image.png
	$(PY) -m cre.cli process "$(FILE)"

regenerate: ## Re-render one variant: make regenerate ASSET=ast_x PROFILE=social_square_1x1
	$(PY) -m cre.cli regenerate "$(ASSET)" "$(PROFILE)"

demo: ## Run both sample assets end to end
	$(PY) -m cre.cli process test_sample/input_image.png --title "Sample Still"
	$(PY) -m cre.cli process test_sample/input_video.mp4 --title "Sample Video"

## ----------------------------------------------------------------- test ----
test: ## Unit tests (fast)
	$(PY) -m pytest backend/tests/unit -q

test-all: ## Every test, including the slow media ones
	$(PY) -m pytest backend/tests -q

coverage: ## Unit tests with a coverage report
	$(PY) -m pytest backend/tests/unit --cov=cre --cov-report=term-missing

lint: ## Ruff + mypy
	$(PY) -m ruff check backend/src backend/tests
	$(PY) -m mypy backend/src/cre

format: ## Autofix with ruff
	$(PY) -m ruff check --fix backend/src backend/tests
	$(PY) -m ruff format backend/src backend/tests

typecheck-web: ## Typecheck the frontend
	cd frontend && npx tsc -b

## ---------------------------------------------------------------- docker ----
up: ## Run the whole stack in Docker
	docker compose up --build

down: ## Stop the Docker stack
	docker compose down -v

## ----------------------------------------------------------------- clean ----
clean: ## Remove generated data (keeps masters out of git anyway)
	rm -rf data/library data/cache data/cre.db

.PHONY: help venv install install-aws models frontend-install setup api web spec \
        process regenerate demo test test-all coverage lint format typecheck-web \
        up down clean
