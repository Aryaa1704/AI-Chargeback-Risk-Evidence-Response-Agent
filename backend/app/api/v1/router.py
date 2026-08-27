"""API v1 router — aggregates all route modules."""

from fastapi import APIRouter

from app.api.v1 import cases, customers, health, risk, seed, transactions

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(seed.router, tags=["seed"])
api_router.include_router(transactions.router)
api_router.include_router(customers.router)
api_router.include_router(cases.router)
api_router.include_router(risk.router)
api_router.include_router(risk.model_router)
