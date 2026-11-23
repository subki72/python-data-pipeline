.PHONY: install lint format typecheck test coverage health run docker-build docker-up docker-down clean

PYTHON ?= python
PIP ?= pip

install:
	$(PIP) install -r requirements.txt

lint:
	flake8 --max-line-length=120 .
	ruff check src tests main.py

format:
	ruff format src tests main.py

typecheck:
	mypy src main.py --ignore-missing-imports

test:
	pytest tests/ -v

coverage:
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=80

health:
	$(PYTHON) main.py --health

run:
	$(PYTHON) main.py

docker-build:
	docker build -t python-data-pipeline:latest .

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage dist build
	find . -type d -name "__pycache__" -exec rm -rf {} +
