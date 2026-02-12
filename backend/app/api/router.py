from fastapi import APIRouter
from app.api import admin, analytics, compare, demo, health, auth, datasets, runs, schema, orgs, invites

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router, prefix="")
api_router.include_router(demo.router, prefix="")
api_router.include_router(auth.router, prefix="")
api_router.include_router(orgs.router, prefix="")
api_router.include_router(invites.router, prefix="")
api_router.include_router(datasets.router, prefix="")
api_router.include_router(runs.router, prefix="")
api_router.include_router(admin.router, prefix="")
api_router.include_router(analytics.router, prefix="")
api_router.include_router(compare.router, prefix="")
api_router.include_router(schema.router, prefix="")