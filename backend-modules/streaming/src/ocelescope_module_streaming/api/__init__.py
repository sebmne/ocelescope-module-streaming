"""The module's HTTP API: one router per resource."""

from fastapi import APIRouter

from ocelescope_module_streaming.api import algorithms, runs

router = APIRouter()
router.include_router(algorithms.router)
router.include_router(runs.router)

__all__ = ["router"]
