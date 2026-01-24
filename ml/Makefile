.PHONY: help build up down logs test clean install

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install Python dependencies locally
	pip install -r requirements.txt

build: ## Build Docker image
	docker build -t swiftbolt-ml-api .

up: ## Start containers with docker-compose
	docker-compose up -d

down: ## Stop containers
	docker-compose down

logs: ## View container logs
	docker-compose logs -f

restart: ## Restart containers
	docker-compose restart

shell: ## Open shell in container
	docker-compose exec fastapi bash

test: ## Run tests
	docker-compose exec fastapi python -m pytest tests/ || echo "No tests directory found"

health: ## Check API health
	curl http://localhost:8000/health

docs: ## Open API documentation
	@echo "Opening API docs at http://localhost:8000/docs"
	@open http://localhost:8000/docs || xdg-open http://localhost:8000/docs || echo "Please open http://localhost:8000/docs in your browser"

clean: ## Remove containers and images
	docker-compose down -v
	docker rmi swiftbolt-ml-api || true

rebuild: clean build ## Clean and rebuild everything

dev: ## Start in development mode with hot-reload
	docker-compose up

prod: build up ## Build and start in production mode
