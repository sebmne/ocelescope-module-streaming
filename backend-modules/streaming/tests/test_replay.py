from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from ocelescope import OCEL
from ocelescope.util.sql import set_utc

from ocelescope_module_streaming.stream import AttributeUpdate, Event, O2OUpdate, ObjectRef, Relation, StreamItem
from ocelescope_module_streaming.stream.ocel import count_items, replay

LOG = Path(__file__).parents[3] / "data" / "event_logs" / "container_logistics.db"
T0, T1, T2 = (datetime(2026, 1, 1) + timedelta(hours=h) for h in range(3))
ORDER, ITEM, CUSTOMER = ObjectRef("o1", "Order"), ObjectRef("i1", "Item"), ObjectRef("c1", "Customer")


@pytest.fixture
def small():
    """e2 and e3 share T1 (e2 first), both before the attribute update at T1."""
    con = duckdb.connect(":memory:")
    set_utc(con)
    con.execute(
        'CREATE TABLE events ("ocel:eid" VARCHAR, "ocel:activity" VARCHAR, "ocel:timestamp" TIMESTAMP, cost DOUBLE)'
    )
    con.execute('CREATE TABLE e2o ("ocel:eid" VARCHAR, "ocel:qualifier" VARCHAR, "ocel:oid" VARCHAR)')
    con.execute('CREATE TABLE objects ("ocel:oid" VARCHAR, "ocel:type" VARCHAR)')
    con.execute('CREATE TABLE o2o ("ocel:oid_1" VARCHAR, "ocel:qualifier" VARCHAR, "ocel:oid_2" VARCHAR)')
    con.execute(
        'CREATE TABLE object_changes ("ocel:oid" VARCHAR, "ocel:timestamp" TIMESTAMP, "ocel:field" VARCHAR, '
        "status VARCHAR, weight DOUBLE)"
    )
    con.executemany(
        "INSERT INTO events VALUES (?, ?, ?, ?)",
        [("e3", "Pick", T1, None), ("e1", "Place", T0, 12.5), ("e2", "Confirm", T1, None), ("e4", "Pay", T2, None)],
    )
    con.executemany(
        "INSERT INTO e2o VALUES (?, ?, ?)",
        [
            ("e1", "placed", "o1"),
            ("e1", "for", "c1"),
            ("e1", None, "i1"),
            ("e2", None, "o1"),
            ("e3", None, "i1"),
            ("e4", None, "o1"),
        ],
    )
    con.executemany("INSERT INTO objects VALUES (?, ?)", [("o1", "Order"), ("i1", "Item"), ("c1", "Customer")])
    con.executemany("INSERT INTO o2o VALUES (?, ?, ?)", [("o1", "contains", "i1"), ("c1", "places", "o1")])
    con.executemany(
        "INSERT INTO object_changes VALUES (?, ?, ?, ?, ?)",
        [("o1", T1, "status", "confirmed", None), ("i1", T2, None, "packed", 3.0)],
    )
    with OCEL(con) as ocel:
        yield ocel


def test_items_are_ordered_by_time_then_kind_then_id(small: OCEL) -> None:
    assert list(replay(small)) == [
        StreamItem(
            Event("Place", (Relation(CUSTOMER, "for"), Relation(ITEM), Relation(ORDER, "placed")), {"cost": 12.5}), T0
        ),
        StreamItem(O2OUpdate(CUSTOMER, ORDER, "places"), T0),  # O2O at the source's first event
        StreamItem(O2OUpdate(ORDER, ITEM, "contains"), T0),
        StreamItem(Event("Confirm", (Relation(ORDER),)), T1),
        StreamItem(Event("Pick", (Relation(ITEM),)), T1),
        StreamItem(AttributeUpdate(ORDER, "status", "confirmed"), T1),
        StreamItem(Event("Pay", (Relation(ORDER),)), T2),
        StreamItem(AttributeUpdate(ITEM, "status", "packed"), T2),  # a field-less change sets every value
        StreamItem(AttributeUpdate(ITEM, "weight", 3.0), T2),
    ]


def test_kinds_can_be_selected(small: OCEL) -> None:
    assert [type(x) for x, _ in replay(small, (Event,))] == [Event] * 4
    assert [type(x) for x, _ in replay(small, (O2OUpdate,))] == [O2OUpdate] * 2
    assert count_items(small, (Event, O2OUpdate)) == 6


def test_the_default_log_is_replayed_completely_in_time_order() -> None:
    if not LOG.exists():
        pytest.skip("default log not downloaded")
    with OCEL.read_duckdb(LOG, read_only=True) as ocel:
        items = list(replay(ocel))
        relations = ocel.sql("SELECT count(*) FROM o2o").fetchall()[0][0]
        changes = ocel.sql("SELECT count(*) FROM object_changes").fetchall()[0][0]
        assert len(items) == count_items(ocel)
    assert Counter(type(x).__name__ for x, _ in items) == {
        "Event": 35_372,
        "O2OUpdate": relations,
        "AttributeUpdate": changes,
    }
    assert [t for _, t in items] == sorted(t for _, t in items)
