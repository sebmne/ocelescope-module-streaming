"""Mapping of domain errors to HTTP responses."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from ocelescope_module_streaming.ocel import UnknownLog
from ocelescope_module_streaming.runs import InvalidRunConfig


def register_exception_handlers(app: FastAPI) -> None:
    """Registers handlers that turn domain errors into JSON error responses."""

    @app.exception_handler(InvalidRunConfig)
    async def invalid_run_config(_: Request, error: InvalidRunConfig) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(error)})

    @app.exception_handler(UnknownLog)
    async def unknown_log(_: Request, error: UnknownLog) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(error)})
