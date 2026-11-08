from fastapi import FastAPI
from ocelescope_backend.app.modules import Module, ModuleMeta
from packaging.version import Version


class Streaming(Module):
    meta = ModuleMeta(key="streaming", version=Version("1.0"))

    def create_app(self) -> FastAPI:
        return FastAPI(title="Streaming", version=str(self.meta.version))
