from fastapi import FastAPI
from ocelescope_backend.app.modules import Module, ModuleMeta
from packaging.version import Version

from ocelescope_module_streaming.api import router
from ocelescope_module_streaming.models import MODELS


class Streaming(Module):
    """Ocelescope module for object-centric process discovery on event streams."""

    meta = ModuleMeta(key="streaming", version=Version("1.0"))
    resources = MODELS

    def create_app(self) -> FastAPI:
        app = FastAPI(title="Streaming", version=str(self.meta.version))
        app.include_router(router)
        return app
