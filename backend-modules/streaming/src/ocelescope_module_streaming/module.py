from fastapi import FastAPI
from ocelescope_backend.app.modules import Module, ModuleMeta
from packaging.version import Version

from ocelescope_module_streaming.api import register_exception_handlers, router
from ocelescope_module_streaming.models import RESOURCES


class Streaming(Module):
    """Ocelescope module for object-centric process discovery on event streams."""

    meta = ModuleMeta(key="streaming", version=Version("1.0"))
    resources = RESOURCES

    def create_app(self) -> FastAPI:
        app = FastAPI(title="Streaming", version=str(self.meta.version))
        register_exception_handlers(app)
        app.include_router(router)
        return app
