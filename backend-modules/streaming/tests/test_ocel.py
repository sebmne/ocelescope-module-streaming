from collections import Counter
from itertools import islice

from ocelescope import OCEL

from ocelescope_module_streaming.ocel import ocel_stream, stream_length
from ocelescope_module_streaming.stream import StreamOptions, well_formed


def test_replay_is_well_formed_and_complete(container_logistics: OCEL) -> None:
    with ocel_stream(container_logistics) as stream:
        kinds = Counter(type(item.x).__name__ for item in well_formed(stream))
    assert kinds == {"Event": 35_372, "AttributeUpdate": 13_048, "O2OUpdate": 15_920}


def test_replay_is_deterministic(container_logistics: OCEL) -> None:
    def head() -> list[object]:
        with ocel_stream(container_logistics) as stream:
            return list(islice(stream, 500))

    assert head() == head()


def test_stream_options_select_item_kinds(container_logistics: OCEL) -> None:
    options = StreamOptions(events=True, object_to_object=False, attribute_updates=False)
    with ocel_stream(container_logistics, options) as stream:
        assert sum(1 for _ in stream) == stream_length(container_logistics, options) == 35_372
