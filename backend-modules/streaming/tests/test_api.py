import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from ocelescope_backend.app.internal.exceptions import NotFound
from ocelescope_backend.app.internal.session import Session
from test_streaming import Counts, EventCounter

from ocelescope_module_streaming.algorithms import ALGORITHMS
from ocelescope_module_streaming.api import router

LOG = Path(__file__).parents[3] / "data" / "event_logs" / "container_logistics.db"


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> Session:
    if not LOG.exists():
        pytest.skip(f"{LOG} not found")
    monkeypatch.setitem(ALGORITHMS, "counter", EventCounter)
    return Session()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_session(request: Request, call_next):
        request.state.session = session
        return await call_next(request)

    with TestClient(app) as client:
        yield client


def wait(client: TestClient, run_id: str) -> dict:
    for _ in range(600):
        run = client.get(f"/runs/{run_id}").json()
        if run["state"] not in ("PENDING", "STARTED"):
            return run
        time.sleep(0.05)
    raise TimeoutError(run_id)


def test_algorithms_come_with_their_config_schema(client: TestClient) -> None:
    algorithms = {a["key"]: a for a in client.get("/algorithms").json()}
    assert algorithms["counter"]["config_schema"]["type"] == "object"


def test_a_run_stores_its_model_and_can_be_deleted(client: TestClient, session: Session) -> None:
    ocel_id = session.add_ocel(LOG, "container")
    started = client.post("/runs", json={"ocel_id": ocel_id, "algorithm": "counter", "snapshot_every": 500})
    assert started.status_code == 201

    run = wait(client, started.json()["id"])
    assert run["state"] == "SUCCESS" and run["name"] == "Event counter on container"
    assert run["processed"] == run["total"] > 0
    snapshot_id = run["snapshot_id"]
    assert session.get_resource(snapshot_id).hidden
    model = session.load_resource(run["result_id"], Counts)
    assert sum(model.counts.values()) == run["total"]
    assert [r["id"] for r in client.get("/runs").json()] == [run["id"]]
    assert client.post(f"/runs/{run['id']}/cancel").status_code == 409

    assert client.delete(f"/runs/{run['id']}").status_code == 204
    assert client.get(f"/runs/{run['id']}").status_code == 404
    assert session.get_resource(run["result_id"])  # the model stays
    with pytest.raises(NotFound):  # the snapshots do not
        session.get_resource(snapshot_id)


def test_unknown_algorithms_and_logs_are_rejected(client: TestClient, session: Session) -> None:
    ocel_id = session.add_ocel(LOG, "container")
    assert client.post("/runs", json={"ocel_id": ocel_id, "algorithm": "nope"}).status_code == 404
    assert client.post("/runs", json={"ocel_id": "nope", "algorithm": "counter"}).status_code == 404
