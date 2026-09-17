PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
BACKEND := PYTHONPATH=backend $(PYTHON)
API_URL ?= http://127.0.0.1:8001

.PHONY: setup verify-env test harness-test check smoke run corpus-scan corpus-deep corpus-heavy

setup:
	$(PYTHON) -m pip install -r backend/requirements.txt

verify-env:
	@$(PYTHON) -c 'import sys; print(f"Python          PASS ({sys.version.split()[0]})")'
	@$(BACKEND) -c 'import fastapi, httpx, pytest, yaml; print("Dependencies    PASS")'
	@mkdir -p "$${RADAR_CACHE_PATH:-/tmp/radar-cache}" && echo "Cache           PASS"
	@$(BACKEND) -c 'from app.core.database import DB_PATH; print(f"Database        PASS ({DB_PATH})")'
	@if [ -n "$${GITHUB_TOKEN:-}" ]; then echo "GitHub auth     PASS (token configured)"; else echo "GitHub auth     WARN (anonymous access)"; fi

test:
	$(BACKEND) -m pytest backend/tests -q

harness-test:
	$(PYTHON) -m pytest scripts/test_validate_corpus.py -q

check: verify-env test harness-test

run:
	RADAR_DB_PATH="$${RADAR_DB_PATH:-/tmp/radar.db}" $(BACKEND) -m uvicorn app.main:app --host 0.0.0.0 --port 8001

smoke:
	$(PYTHON) validation/runner.py --mode smoke --base-url $(API_URL)

corpus-scan:
	$(PYTHON) validation/runner.py --mode scan --base-url $(API_URL)

corpus-deep:
	$(PYTHON) validation/runner.py --mode deep --base-url $(API_URL)

corpus-heavy:
	$(PYTHON) validation/runner.py --mode scan --tag large --timeout 600 --base-url $(API_URL)
