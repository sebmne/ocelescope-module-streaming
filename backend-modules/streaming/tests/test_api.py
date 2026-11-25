import time
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ocelescope import OCEL
from ocelescope_backend.app.dependencies import get_session
from ocelescope_backend.app.internal.exceptions import NotFound
from support import LOG_PATH

from ocelescope_module_streaming.api.presets import PRESETS
from ocelescope_module_streaming.api.routes import router
from ocelescope_module_streaming.framework import ALGORITHMS


class FakeHandle:
    def open(self) -> OCEL:
        return OCEL.read_duckdb(LOG_PATH, read_only=True)


class FakeSession:
    def __init__(self) -> None:
        self.id = str(uuid.uuid4())
        self.resources: list[tuple[Any, str]] = []

    def get_ocel(self, ocel_id: str) -> FakeHandle:
        if ocel_id != "log":
            raise NotFound(ocel_id)
        return FakeHandle()

    def add_resource(self, resource: Any, name: str) -> str:
        self.resources.append((resource, name))
        return f"r{len(self.resources)}"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    session = FakeSession()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def wait_for(client: TestClient, replay_id: str, states: set[str], timeout: float = 30) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/replays/{replay_id}").json()
        if status["state"] in states:
            return status
        time.sleep(0.05)
    raise AssertionError(f"Replay did not reach {states}")


def test_catalog_lists_algorithms_heuristics_and_presets(client: TestClient) -> None:
    catalog = client.get("/catalog").json()
    assert {a["key"] for a in catalog["algorithms"]} == set(ALGORITHMS)
    lifecycle = next(h for h in catalog["heuristics"] if h["name"] == "lifecycle")
    assert lifecycle["needs_lifecycle_values"]
    assert [p["capacity"] for p in lifecycle["private_buffers"]] == ["c", "c_hist"]
    assert len(catalog["presets"]) == len(PRESETS)


@pytest.mark.parametrize("preset", PRESETS, ids=lambda p: p.key)
def test_presets_are_valid(client: TestClient, preset: Any) -> None:
    config = {"ocel_id": "log", "algorithm": preset.algorithm, "params": preset.params, "speed": 0}
    config["buffers"] = {name: buffer.model_dump() for name, buffer in preset.buffers.items()}
    response = client.post("/replays", json=config)
    assert response.status_code == 201, response.text
    status = wait_for(client, response.json()["id"], {"finished", "failed"}, timeout=120)
    assert status["state"] == "finished", status["error"]
    assert all(b["capacity"] is None or b["size"] <= b["capacity"] for b in status["buffers"])
    model = client.get(f"/replays/{status['id']}/model").json()
    assert model["position"] == status["position"] == status["total"]
    assert model["visualization"]["type"] in {"r4pm_ocdfg", "graph"}


def test_replays_can_be_paused_paced_resumed_and_cancelled(client: TestClient) -> None:
    replay = client.post("/replays", json={"ocel_id": "log", "algorithm": "liss_totem", "speed": 500}).json()
    wait_for(client, replay["id"], {"running"})
    client.post(f"/replays/{replay['id']}/control", json={"action": "pause"})
    time.sleep(0.3)
    paused = client.get(f"/replays/{replay['id']}").json()
    time.sleep(0.3)
    assert client.get(f"/replays/{replay['id']}").json()["position"] <= paused["position"] + 1
    client.post(f"/replays/{replay['id']}/control", json={"action": "speed", "speed": 0})
    client.post(f"/replays/{replay['id']}/control", json={"action": "resume"})
    time.sleep(0.2)
    client.post(f"/replays/{replay['id']}/control", json={"action": "cancel"})
    status = wait_for(client, replay["id"], {"cancelled", "finished"})
    assert status["position"] > paused["position"]
    assert status["fill"]["positions"]
    assert [r["id"] for r in client.get("/replays").json()] == [replay["id"]]


def test_the_current_model_can_be_saved(client: TestClient) -> None:
    replay = client.post("/replays", json={"ocel_id": "log", "algorithm": "df", "speed": 0}).json()
    wait_for(client, replay["id"], {"finished"})
    assert client.post(f"/replays/{replay['id']}/save").json() == {"resource_id": "r1"}


def test_invalid_configurations_are_rejected(client: TestClient) -> None:
    lifecycle_rows = {"arcs": {"capacity": 10, "heuristic": {"name": "lifecycle"}}}
    assert (
        client.post(
            "/replays", json={"ocel_id": "log", "algorithm": "liss_ocdfg", "buffers": lifecycle_rows}
        ).status_code
        == 422
    )
    assert client.post("/replays", json={"ocel_id": "log", "algorithm": "nope"}).status_code == 422
    assert client.post("/replays", json={"ocel_id": "other", "algorithm": "df"}).status_code == 404
    assert client.get("/replays/unknown").status_code == 404
