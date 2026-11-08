"""Object-centric event streams.

A stream is an iterable of `StreamItem` pairs ``(x, t)``, consumed once from front to back.
Sources produce streams lazily, so a stream may be infinite. Algorithms do not iterate streams
themselves; the framework's run loop passes them one item at a time.
"""

from collections.abc import Iterable

from ocelescope_module_streaming.stream.items import (
    AttributeUpdate,
    AttributeValue,
    Content,
    Event,
    O2OUpdate,
    ObjectRef,
    Relation,
    StreamItem,
)
from ocelescope_module_streaming.stream.options import StreamOptions
from ocelescope_module_streaming.stream.well_formed import MalformedStream, well_formed

Stream = Iterable[StreamItem]

__all__ = [
    "AttributeUpdate",
    "AttributeValue",
    "Content",
    "Event",
    "MalformedStream",
    "O2OUpdate",
    "ObjectRef",
    "Relation",
    "Stream",
    "StreamItem",
    "StreamOptions",
    "well_formed",
]
