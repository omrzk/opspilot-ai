.PHONY: up down logs test-backend lint-backend test-frontend build dev-backend dev-frontend

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api worker

test-backend:
	cd backend && python -m pytest -q

lint-backend:
	cd backend && ruff check app tests

test-frontend:
	cd frontend && npm run lint && npx tsc --noEmit

build:
	docker compose build

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev
