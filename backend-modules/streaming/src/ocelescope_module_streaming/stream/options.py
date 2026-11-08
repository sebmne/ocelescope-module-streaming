from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StreamOptions:
    """Selects which item kinds a stream contains.

    Attributes:
        events: Whether to include events.
        object_to_object: Whether to include object-to-object updates.
        attribute_updates: Whether to include attribute updates.
    """

    events: bool = True
    object_to_object: bool = True
    attribute_updates: bool = True
