from fastapi import FastAPI
from fastapi.testclient import TestClient

from ocelescope_module_streaming.routes import router


def test_hello() -> None:
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from the Streaming backend module"}
