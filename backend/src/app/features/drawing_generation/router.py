from fastapi import APIRouter

from .artifacts import lifespan
from .routes import generation, inspection, key_plan

router = APIRouter(lifespan=lifespan)
router.include_router(generation.router)
router.include_router(inspection.router)
router.include_router(key_plan.router)
