from pathlib import Path

import pytest
from ocelescope import OCEL
from support import event, o2o, obj, stream_of

from ocelescope_module_streaming.stream import StreamItem

LOGS = Path(__file__).resolve().parents[3] / "data" / "event_logs"


@pytest.fixture
def surgery_stream() -> list[StreamItem]:
    """The stream fragment of Mühlmeyer et al. 2026, Table 1: surgery diverges on doctor."""
    return stream_of(
        event("surgery", doctor="D1", patient="PatA"),
        event("surgery", doctor="D2", patient="PatB"),
        event("surgery", doctor="D2", patient="PatC"),
    )


@pytest.fixture
def order_stream() -> list[StreamItem]:
    """The running example of Liss et al. 2025, Table 1 (events e1-e5 and the O2O relation)."""
    return stream_of(
        event("Place order", customer="c1", order="o1", item=["i1", "i2"]),
        event("Pick item", order="o1", item="i2"),
        event("Pick item", order="o1", item="i1"),
        event("Package", order="o1", parcel="p1"),
        event("Label", **{"shipping label": "l1"}),
        o2o(obj("parcel", "p1"), obj("shipping label", "l1"), "labeled"),
    )


@pytest.fixture(scope="session")
def container_logistics() -> OCEL:
    """The Container Logistics OCEL shipped in `data/`."""
    path = LOGS / "container_logistics.db"
    if not path.exists():
        pytest.skip(f"{path} not found")
    return OCEL.read_duckdb(str(path))
