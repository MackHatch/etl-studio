# ETL Studio - root development commands
# Prerequisites: Docker, uv (Python), node 20+ (frontend)

.PHONY: dev reset seed demo help up down

help:
	@echo "ETL Studio - available targets:"
	@echo "  make demo  - One-command demo: reset + seed + start app (prints URLs & creds)"
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
# Optional: ADMIN_EMAIL, ADMIN_PASSWORD (e.g. make reset ADMIN_EMAIL=admin@acme.com ADMIN_PASSWORD=DemoPass123!)
reset: down
	@echo ">>> Starting postgres for reset..."
	@docker compose up -d postgres redis
	@sleep 5
	@echo ">>> Resetting migrations..."
	@cd backend && uv run alembic downgrade base 2>/dev/null || true
	@cd backend && uv run alembic upgrade head
	@echo ">>> Seeding demo..."
	@ADMIN_EMAIL="$(or $(ADMIN_EMAIL),admin@example.com)" \
	 ADMIN_PASSWORD="$(or $(ADMIN_PASSWORD),adminpassword)" \
	 DATABASE_URL=postgresql+asyncpg://etl_user:etl_password@localhost:5432/etl_db \
	 REDIS_URL=redis://localhost:6379/0 \
	 JWT_SECRET=dev-secret \
	 SEED_DEMO=true \
	 uv run --package backend python backend/scripts/reset_and_seed.py
	@echo ">>> Reset complete. Run 'make dev' to start full stack."

# Seed demo only (DB must be up)
seed:
	@uv run --package backend python backend/scripts/reset_and_seed.py

# One-command demo: reset DB, seed Acme demo, start full stack, print URLs + creds
demo:
	$(MAKE) reset ADMIN_EMAIL=admin@acme.com ADMIN_PASSWORD=DemoPass123!
	@echo ""
	@echo "========================================"
	@echo "  2-MINUTE DEMO - ETL Studio"
	@echo "========================================"
	@echo ""
	@echo "  App:       http://localhost:3000"
	@echo "  API docs:  http://localhost:8000/docs"
	@echo "  Flower:    http://localhost:5555"
	@echo "  MinIO:     http://localhost:9001"
	@echo ""
	@echo "  Demo login:"
	@echo "    admin@acme.com   / DemoPass123!  (ADMIN)"
	@echo "    analyst@acme.com / DemoPass123!  (ADMIN)"
	@echo "    member@acme.com  / DemoPass123!  (MEMBER)"
	@echo ""
	@echo "  Starting full stack..."
	@echo ""
	@docker compose up --build
