from fastapi import FastAPI
from ocelescope_backend.app.modules import Module, ModuleMeta
from packaging.version import Version

from ocelescope_module_streaming.api.routes import router
from ocelescope_module_streaming.models import Totem


class Streaming(Module):
    meta = ModuleMeta(key="streaming", version=Version("1.0"))
    resources = [Totem]

    def create_app(self) -> FastAPI:
        app = FastAPI(title="Streaming", version=str(self.meta.version))
        app.include_router(router)
        return app
