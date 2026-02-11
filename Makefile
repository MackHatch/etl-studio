# ETL Studio - root development commands
# Prerequisites: Docker, uv (Python), node 20+ (frontend)

.PHONY: dev reset seed help up down

help:
	@echo "ETL Studio - available targets:"
	@echo "  make dev   - Start full stack (docker compose up)"
	@echo "  make reset - Reset DB, run migrations, seed demo"
	@echo "  make seed  - Seed demo data (requires DB up, SEED_DEMO=true)"
	@echo "  make up    - docker compose up -d"
	@echo "  make down  - docker compose down"

# Start full development stack
dev:
	docker compose up --build

# Docker compose up (detached)
up:
	docker compose up -d
	@echo ">>> Waiting for postgres..."
	@sleep 5

# Docker compose down
down:
	docker compose down

# Reset database: downgrade, upgrade, seed demo
reset: down
	@echo ">>> Starting postgres for reset..."
	@docker compose up -d postgres redis
	@sleep 5
	@echo ">>> Resetting migrations..."
	@cd backend && uv run alembic downgrade base 2>/dev/null || true
	@cd backend && uv run alembic upgrade head
	@echo ">>> Seeding demo..."
	@DATABASE_URL=postgresql+asyncpg://etl_user:etl_password@localhost:5432/etl_db REDIS_URL=redis://localhost:6379/0 JWT_SECRET=dev-secret uv run --package backend python backend/scripts/reset_and_seed.py
	@echo ">>> Reset complete. Run 'make dev' to start full stack."

# Seed demo only (DB must be up)
seed:
	@uv run --package backend python backend/scripts/reset_and_seed.py
