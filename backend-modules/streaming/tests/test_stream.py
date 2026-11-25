from itertools import islice

import pytest
from ocelescope import OCEL
from support import ITEM, LOG_PATH, ORDER, running_example

from ocelescope_module_streaming.stream import (
    AttributeUpdate,
    Event,
    NotWellFormed,
    O2OUpdate,
    StreamItem,
    StreamOptions,
    TypedObject,
    event,
    is_well_formed,
    obj,
    tobj,
    well_formed,
)
from ocelescope_module_streaming.stream.ocel import ocel_stream, stream_length


def test_typed_objects_of_each_item_kind() -> None:
    assert tobj(event("place", [("o1", ORDER), ("i1", ITEM)], 1)) == (TypedObject("o1", ORDER), TypedObject("i1", ITEM))
    o2o = StreamItem(O2OUpdate("o1", ORDER, "contains", "i1", ITEM), 1)
    assert obj(o2o) == ("o1", "i1")
    update = StreamItem(AttributeUpdate("o1", ORDER, "price", 3), 1)
    assert tobj(update) == (TypedObject("o1", ORDER),)


def test_duplicate_relations_yield_each_object_once() -> None:
    item = event("place", [("o1", ORDER), ("o1", ORDER)], 1)
    assert obj(item) == ("o1",)


def test_running_example_is_well_formed() -> None:
    stream = running_example()
    assert len(stream) == 9
    assert is_well_formed(stream)


def test_decreasing_timestamps_are_rejected() -> None:
    with pytest.raises(NotWellFormed) as error:
        list(well_formed([event("a", [("o1", ORDER)], 2), event("b", [("o1", ORDER)], 1)]))
    assert error.value.position == 2


def test_changing_object_types_are_rejected() -> None:
    assert not is_well_formed([event("a", [("o1", ORDER)], 1), event("b", [("o1", ITEM)], 1)])


@pytest.fixture(scope="module")
def ocel():
    log = OCEL.read_duckdb(LOG_PATH, read_only=True)
    yield log
    log.close()


def test_replay_is_well_formed_and_complete(ocel: OCEL) -> None:
    options = StreamOptions(events=True, o2o_updates=True, attribute_updates=False)
    with ocel_stream(ocel, options) as stream:
        items = list(well_formed(stream))
    assert len(items) == stream_length(ocel, options)
    kinds = {type(item.x) for item in items}
    assert kinds == {Event, O2OUpdate}


def test_replay_orders_events_before_o2o_updates_at_equal_times(ocel: OCEL) -> None:
    with ocel_stream(ocel) as stream:
        items = list(islice(stream, 5000))
    for before, after in zip(items, items[1:], strict=False):
        if before.t == after.t and isinstance(before.x, O2OUpdate):
            assert not isinstance(after.x, Event)


def test_replay_is_deterministic(ocel: OCEL) -> None:
    with ocel_stream(ocel) as first, ocel_stream(ocel) as second:
        assert list(islice(first, 2000)) == list(islice(second, 2000))


def test_event_kinds_can_be_left_out(ocel: OCEL) -> None:
    with ocel_stream(ocel, StreamOptions(events=False, o2o_updates=False, attribute_updates=True)) as stream:
        assert all(isinstance(item.x, AttributeUpdate) for item in islice(stream, 1000))
