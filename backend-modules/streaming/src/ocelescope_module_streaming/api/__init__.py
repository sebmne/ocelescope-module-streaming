"""HTTP API of the streaming module."""

from fastapi import APIRouter

from ocelescope_module_streaming.api.errors import register_exception_handlers
from ocelescope_module_streaming.api.routes import catalog, runs

router = APIRouter()
router.include_router(catalog.router)
router.include_router(runs.router)

__all__ = ["register_exception_handlers", "router"]
