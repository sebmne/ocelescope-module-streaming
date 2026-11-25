from fastapi import FastAPI
from ocelescope_backend.app.modules import Module, ModuleMeta
from packaging.version import Version

from ocelescope_module_streaming.routes import router


class Streaming(Module):
    meta = ModuleMeta(key="streaming", version=Version("1.0"))

    def create_app(self) -> FastAPI:
        app = FastAPI(title="Streaming", version=str(self.meta.version))
        app.include_router(router)
        return app
