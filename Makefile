.PHONY: help install install-dev setup clean test test-cov lint format type-check security run dev migrate upgrade downgrade docker-build docker-run docker-stop logs backup restore deploy

# Default target
help:
	@echo "SST Platform - Available commands:"
	@echo ""
	@echo "Setup and Installation:"
	@echo "  install      Install production dependencies"
	@echo "  install-dev  Install development dependencies"
	@echo "  setup        Complete development setup"
	@echo "  clean        Clean cache and temporary files"
	@echo ""
	@echo "Development:"
	@echo "  run          Run development server"
	@echo "  dev          Run development server with auto-reload"
	@echo "  test         Run tests"
	@echo "  test-cov     Run tests with coverage"
	@echo "  lint         Run linting checks"
	@echo "  format       Format code"
	@echo "  type-check   Run type checking"
	@echo "  security     Run security checks"
	@echo ""
	@echo "Database:"
	@echo "  migrate      Create new migration"
	@echo "  upgrade      Apply migrations"
	@echo "  downgrade    Rollback migrations"
	@echo "  backup       Backup database"
	@echo "  restore      Restore database"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build Build Docker image"
	@echo "  docker-run   Run with Docker Compose"
	@echo "  docker-stop  Stop Docker containers"
	@echo "  logs         Show Docker logs"
	@echo ""
	@echo "Deployment:"
	@echo "  deploy       Deploy to production"

# Installation
install:
	poetry install --only=main

install-dev:
	poetry install

setup: install-dev
	@echo "Setting up development environment..."
	@mkdir -p uploads logs certificates static templates
	@cp .env.example .env
	@echo "Please configure your .env file"
	pre-commit install
	@echo "Development environment setup complete!"

# Cleaning
clean:
	@echo "Cleaning cache and temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/ .tox/
	@echo "Cleanup complete!"

# Development
run:
	poetry run uvicorn main:app --host 0.0.0.0 --port 8000

dev:
	poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Testing
test:
	poetry run pytest

test-cov:
	poetry run pytest --cov=app --cov-report=html --cov-report=term

test-watch:
	poetry run ptw -- --testmon

# Code Quality
lint:
	@echo "Running linting checks..."
	poetry run flake8 app/
	poetry run black --check app/
	poetry run isort --check-only app/

format:
	@echo "Formatting code..."
	poetry run black app/
	poetry run isort app/
	poetry run autoflake --in-place --remove-all-unused-imports --recursive app/

type-check:
	poetry run mypy app/

security:
	@echo "Running security checks..."
	poetry run bandit -r app/
	poetry run safety check

check-all: lint type-check security test
	@echo "All checks completed!"

# Database
migrate:
	@read -p "Enter migration message: " msg; \
	poetry run alembic revision --autogenerate -m "$$msg"

upgrade:
	poetry run alembic upgrade head

downgrade:
	@read -p "Enter number of revisions to rollback (default 1): " revs; \
	revs=$${revs:-1}; \
	poetry run alembic downgrade -$$revs

db-reset:
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		poetry run alembic downgrade base; \
		poetry run alembic upgrade head; \
		echo "Database reset complete!"; \
	else \
		echo "Operation cancelled."; \
	fi

# Backup and Restore
backup:
	@echo "Creating database backup..."
	@mkdir -p backups
	@timestamp=$$(date +"%Y%m%d_%H%M%S"); \
	pg_dump $${DATABASE_URL:-postgresql://sst_user:sst_password@localhost:5432/sst_platform} > backups/backup_$$timestamp.sql
	@echo "Backup created: backups/backup_$$timestamp.sql"

restore:
	@echo "Available backups:"
	@ls -la backups/*.sql 2>/dev/null || echo "No backups found"
	@read -p "Enter backup filename: " backup; \
	if [ -f "backups/$$backup" ]; then \
		psql $${DATABASE_URL:-postgresql://sst_user:sst_password@localhost:5432/sst_platform} < backups/$$backup; \
		echo "Database restored from $$backup"; \
	else \
		echo "Backup file not found!"; \
	fi

# Docker
docker-build:
	docker build -t sst-platform .

docker-run:
	docker-compose up -d

docker-dev:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

docker-stop:
	docker-compose down

docker-clean:
	docker-compose down -v --remove-orphans
	docker system prune -f

logs:
	docker-compose logs -f

logs-app:
	docker-compose logs -f app

logs-db:
	docker-compose logs -f db

# Production
deploy:
	@echo "Deploying to production..."
	@echo "1. Building Docker image..."
	make docker-build
	@echo "2. Running tests..."
	make test
	@echo "3. Pushing to registry..."
	# docker push your-registry/sst-platform:latest
	@echo "4. Deploying..."
	# Add your deployment commands here
	@echo "Deployment complete!"

# Monitoring
status:
	@echo "=== Application Status ==="
	@curl -s http://localhost:8000/health | jq . || echo "Application not responding"
	@echo ""
	@echo "=== Docker Status ==="
	@docker-compose ps

monitor:
	@echo "Monitoring application logs..."
	@echo "Press Ctrl+C to stop"
	tail -f logs/app.log

# Documentation
docs:
	@echo "Starting documentation server..."
	@echo "API docs available at: http://localhost:8000/docs"
	@echo "ReDoc available at: http://localhost:8000/redoc"
	make dev

# Utilities
shell:
	poetry shell

requirements:
	poetry export -f requirements.txt --output requirements.txt --without-hashes

update:
	poetry update
	pre-commit autoupdate

# Environment
env-check:
	@echo "Checking environment configuration..."
	@poetry run python -c "from app.config import settings; print('✅ Configuration loaded successfully')"

env-example:
	@echo "Updating .env.example with current configuration..."
	@poetry run python -c "\
	from app.config import Settings; \
	import inspect; \
	fields = Settings.__fields__; \
	with open('.env.example', 'w') as f: \
		for name, field in fields.items(): \
			f.write(f'{name.upper()}={field.default}\n')\
	"

# Help for specific commands
help-docker:
	@echo "Docker Commands Help:"
	@echo "  docker-build: Build the application Docker image"
	@echo "  docker-run:   Start all services with Docker Compose"
	@echo "  docker-dev:   Start services in development mode"
	@echo "  docker-stop:  Stop all running containers"
	@echo "  docker-clean: Stop containers and remove volumes"
	@echo "  logs:         Show logs from all services"
	@echo "  logs-app:     Show logs from application only"
	@echo "  logs-db:      Show logs from database only"

help-db:
	@echo "Database Commands Help:"
	@echo "  migrate:   Create a new migration file"
	@echo "  upgrade:   Apply pending migrations"
	@echo "  downgrade: Rollback migrations"
	@echo "  db-reset:  Reset database (WARNING: deletes all data)"
	@echo "  backup:    Create database backup"
	@echo "  restore:   Restore from backup"

help-dev:
	@echo "Development Commands Help:"
	@echo "  setup:      Complete development environment setup"
	@echo "  dev:        Start development server with auto-reload"
	@echo "  test:       Run test suite"
	@echo "  test-cov:   Run tests with coverage report"
	@echo "  lint:       Check code style and quality"
	@echo "  format:     Auto-format code"
	@echo "  type-check: Run static type checking"
	@echo "  security:   Run security vulnerability checks"