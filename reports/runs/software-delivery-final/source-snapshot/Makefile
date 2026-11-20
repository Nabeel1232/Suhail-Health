SHELL := /bin/bash
ENV_FILE ?= $(CURDIR)/.env
export ENV_FILE_PATH := $(ENV_FILE)
export NEXT_TELEMETRY_DISABLED := 1
export PATH := $(CURDIR)/.runtime/node/bin:$(PATH)
PY := $(CURDIR)/.venv/bin/python
PRESET ?= smoke
DATASET ?= healthbench_adapted
EVAL_ARGS ?=
.PHONY: setup doctor build up down status migrate seed test test-e2e demo-replay eval-fetch eval-offline eval-live reports fresh-check verification-report compose-up
setup:
	bash scripts/setup.sh
doctor:
	$(PY) scripts/doctor.py
build:
	cd apps/web && npm run build
up:
	$(PY) scripts/local.py up
down:
	$(PY) scripts/local.py down
status:
	$(PY) scripts/local.py status
migrate:
	$(PY) -c 'from services.api.db import init_db; init_db(); print("Schema migration ready")'
seed:
	$(PY) -m services.api.seed
test:
	$(PY) -m pytest tests -q --ignore=tests/test_browser.py --ignore=tests/test_browser_care.py --junitxml=runtime/test-results.xml
test-e2e:
	$(PY) scripts/reset_demo.py
	$(PY) -m pytest tests/test_browser.py tests/test_browser_care.py -q --junitxml=runtime/browser-results.xml
demo-replay:
	$(PY) scripts/demo_replay.py
eval-fetch:
	$(PY) -m evals.runner fetch --dataset $(DATASET)
eval-offline:
	$(PY) -m evals.runner offline
eval-live:
	$(PY) -m evals.runner live --preset $(PRESET) $(EVAL_ARGS)
reports:
	$(PY) -m evals.runner reports --run-id $(RUN_ID)
compose-up:
	bash scripts/compose.sh --env-file .runtime/app.env up --build -d
verification-report:
	$(PY) scripts/verification_report.py
fresh-check:
	$(PY) scripts/fresh_check.py
