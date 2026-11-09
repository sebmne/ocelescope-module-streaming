"""Divergence detection (definitions.tex: def:divergence)."""

from typing import Any

from ocelescope_module_streaming.framework import Buffer
from ocelescope_module_streaming.stream import Event, ObjectRef

IndexKey = tuple[str, str, int]
"""(activity, object type, hash of the event's objects of that type)."""


class DivergenceIndex:
    """Detects divergent activity–type pairs.

    An activity a diverges for type t if two events of a agree on their objects of type t but
    differ in their full object sets. The index stores, per (a, t, h(O⇂t)), the hash h(O) of the
    first full object set seen. A different full hash under the same key marks (a, t) as
    divergent, after which its index entries are discarded and (a, t) is no longer tracked.

    Args:
        index: The divergence index, keyed by `IndexKey`, with full-set hashes as values.
        divergent: The divergent pairs (a, t); never evicted in practice since it is small.
    """

    def __init__(self, index: Buffer[IndexKey, int], divergent: Buffer[tuple[str, str], bool]) -> None:
        self.index = index
        self.divergent = divergent
        self._keys: dict[tuple[str, str], set[IndexKey]] = {}  # index keys per (a, t), to discard them

    def update(self, event: Event) -> None:
        """Processes an event."""
        objects = frozenset(event.objects)
        full = _hash(objects)
        by_type: dict[str, set[ObjectRef]] = {}
        for obj in objects:
            by_type.setdefault(obj.type, set()).add(obj)
        for object_type, typed in by_type.items():
            pair = (event.activity, object_type)
            if pair in self.divergent:
                continue
            key = (event.activity, object_type, _hash(typed))
            stored = self.index.get(key)
            if stored is not None and stored != full:
                self.divergent.put(pair, True)
                for discarded in self._keys.pop(pair, ()):
                    self.index.discard(discarded)
            else:
                self.index.put(key, full)
                self._keys.setdefault(pair, set()).add(key)

    def finish(self, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:
        """Forgets an evicted index key."""
        if buffer is self.index:
            keys = self._keys.get(key[:2])
            if keys is not None:
                keys.discard(key)
                if not keys:
                    del self._keys[key[:2]]

    def snapshot(self) -> frozenset[tuple[str, str]]:
        """Returns the divergent pairs (a, t)."""
        return frozenset(self.divergent)


def _hash(objects: frozenset[ObjectRef] | set[ObjectRef]) -> int:
    return hash(frozenset(obj.id for obj in objects))
