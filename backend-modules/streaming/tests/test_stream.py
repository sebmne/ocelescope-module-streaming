from datetime import timedelta

import pytest
from support import START, event, obj, stream_of

from ocelescope_module_streaming.stream import MalformedStream, StreamItem, well_formed


def test_well_formed_passes_items_through(order_stream: list[StreamItem]) -> None:
    assert list(well_formed(order_stream)) == order_stream


def test_well_formed_rejects_decreasing_timestamps() -> None:
    stream = stream_of(event("a", t="x"), event("b", t="x"), step=timedelta(days=-1))
    with pytest.raises(MalformedStream) as error:
        list(well_formed(stream))
    assert error.value.position == 2


def test_well_formed_rejects_type_changes() -> None:
    stream = [StreamItem(event("a", order="x"), START), StreamItem(event("b", item="x"), START)]
    with pytest.raises(MalformedStream, match="type item"):
        list(well_formed(stream))


def test_event_objects_keep_relation_order() -> None:
    assert event("a", order="o1", item=["i1", "i2"]).objects == (
        obj("order", "o1"),
        obj("item", "i1"),
        obj("item", "i2"),
    )
