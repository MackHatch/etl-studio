# ETL Studio - root development commands
# Prerequisites: Docker, uv (Python), node 20+ (frontend)

.PHONY: dev reset seed demo help up down

help:
	@echo "ETL Studio - available targets:"
	@echo "  make demo  - One-command: up -d, migrate, seed, start (prints URLs)"
	@echo "  make dev   - Start full stack (docker compose up)"
	@echo "  make reset - Down -v, up, migrate, seed (drop volumes)"
	@echo "  make seed  - Seed demo (DB must be up, SEED_DEMO=true)"
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

# Reset: drop volumes, up, migrate, seed
reset: down
	@docker compose down -v 2>/dev/null || true
	@echo ">>> Starting postgres, redis, minio..."
	@docker compose up -d postgres redis minio minio-init
	@echo ">>> Waiting for postgres..."
	@sleep 5
	@echo ">>> Migrating..."
	@cd backend && uv run alembic upgrade head
	@echo ">>> Seeding demo..."
	@ADMIN_EMAIL="$(or $(ADMIN_EMAIL),demo@etl.com)" \
	 ADMIN_PASSWORD="$(or $(ADMIN_PASSWORD),DemoPass123!)" \
	 DATABASE_URL=postgresql+asyncpg://etl_user:etl_password@localhost:5432/etl_db \
	 REDIS_URL=redis://localhost:6379/0 \
	 JWT_SECRET=dev-secret \
	 SEED_DEMO=true \
	 uv run --package backend python backend/scripts/reset_and_seed.py
	@echo ">>> Reset complete. Run 'make dev' to start full stack."

# Seed demo only (DB must be up)
seed:
	@ADMIN_EMAIL="$(or $(ADMIN_EMAIL),demo@etl.com)" \
	 ADMIN_PASSWORD="$(or $(ADMIN_PASSWORD),DemoPass123!)" \
	 SEED_DEMO=true \
	 uv run --package backend python backend/scripts/reset_and_seed.py

# One-command demo: compose up -d, migrate, seed, start, print URLs
demo:
	@echo ">>> Starting services (postgres, redis, minio, otel, jaeger, flower)..."
	@docker compose up -d postgres redis minio minio-init otel-collector jaeger flower
	@echo ">>> Waiting for postgres..."
	@sleep 5
	@echo ">>> Migrating..."
	@cd backend && uv run alembic upgrade head
	@echo ">>> Seeding demo..."
	@ADMIN_EMAIL=demo@etl.com \
	 ADMIN_PASSWORD=DemoPass123! \
	 DATABASE_URL=postgresql+asyncpg://etl_user:etl_password@localhost:5432/etl_db \
	 REDIS_URL=redis://localhost:6379/0 \
	 JWT_SECRET=dev-secret \
	 SEED_DEMO=true \
	 uv run --package backend python backend/scripts/reset_and_seed.py
	@echo ""
	@echo "========================================"
	@echo "  2-MINUTE DEMO - ETL Studio"
	@echo "========================================"
	@echo ""
	@echo "  App:        http://localhost:3000"
	@echo "  Demo page:  http://localhost:3000/demo"
	@echo "  API docs:   http://localhost:8000/docs"
	@echo "  Flower:     http://localhost:5555"
	@echo "  MinIO:      http://localhost:9001"
	@echo "  Jaeger:     http://localhost:16686"
	@echo ""
	@echo "  Login: demo@etl.com / DemoPass123!"
	@echo ""
	@echo "  Starting backend + worker + frontend..."
	@echo ""
	@docker compose up --build backend worker frontend
