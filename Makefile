.DEFAULT_GOAL := help
.PHONY: help logs test docker-test stop build up up-view install setup run admin web view \
	frontend-install frontend-build frontend-dev

# Use the local virtualenv's interpreter when present (venv/ or .venv/),
# otherwise fall back to `python` on PATH (e.g. inside the Docker image).
PYTHON := $(shell if [ -x venv/bin/python ]; then echo venv/bin/python; \
	elif [ -x .venv/bin/python ]; then echo .venv/bin/python; \
	else echo python; fi)
PYTEST := $(shell if [ -x venv/bin/pytest ]; then echo venv/bin/pytest; \
	elif [ -x .venv/bin/pytest ]; then echo .venv/bin/pytest; \
	else echo pytest; fi)

help:
	@perl -nle'print $& if m{^[a-zA-Z_-]+:.*?## .*$$}' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

install: ## install all Python dependencies (local dev)
	pip install uv 2>/dev/null || true
	uv pip install -r requirements/local.txt

setup: install ## install deps + Playwright browsers + migrate + bootstrap CRM
	playwright install --with-deps chromium
	$(PYTHON) manage.py migrate --no-input
	$(PYTHON) manage.py setup_crm

run: ## run the daemon (task queue worker)
	$(PYTHON) manage.py rundaemon

test: ## run the test suite
	$(PYTEST)

# Control center web app (React SPA + DRF API)
frontend-install: ## install the React SPA dependencies
	cd frontend && npm install

frontend-build: ## build the React SPA into frontend/dist (served by Django)
	cd frontend && npm run build

frontend-dev: ## run the Vite dev server (proxies /api to localhost:8000 — run `make web` too)
	cd frontend && npm run dev

web: ## serve the control center (SPA + API) — build the SPA first with `make frontend-build`
	@echo ""
	@echo "  Control center: http://localhost:8000/"
	@echo "  Django Admin:   http://localhost:8000/admin/"
	@echo ""
	$(PYTHON) manage.py runserver

admin: web ## alias for `make web` (control center + admin)

# Docker targets
logs: ## follow the logs of the service
	docker compose -f local.yml logs -f

docker-test: ## run tests in Docker
	docker compose -f local.yml run --remove-orphans app py.test -vv -p no:cacheprovider

stop: ## stop all services defined in Docker Compose
	docker compose -f local.yml stop

build: ## build all services defined in Docker Compose
	docker compose -f local.yml build

up: ## run the defined service in Docker Compose
	docker compose -f local.yml up --build -d
	docker compose -f local.yml logs -f

up-view: ## run the defined service in Docker Compose and open vinagre
	docker compose -f local.yml up --build -d
	sleep 3
	$(MAKE) view
	docker compose -f local.yml logs -f app

view: ## open vinagre to view the app
	@sh -c 'vinagre vnc://127.0.0.1:5900 > /dev/null 2>&1 &'
