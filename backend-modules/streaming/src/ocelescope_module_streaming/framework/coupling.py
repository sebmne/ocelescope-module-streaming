"""Coupled removal: optional consistency between buffers after evictions.

When ins evicts an entry (k*, v*) from a buffer B1, the entry is returned to the algorithm. An
algorithm that wants its buffers to stay consistent hands it to a `CoupledRemoval`, which
deletes the entries of the same objects (or object types) from the other buffers, as the buffer
synchronization of Liss et al. does.

Each coupled buffer comes with a function that maps an entry to the members it belongs to, e.g.
the object of an entry or its object types. After the evictions of an item, `sync` takes every
member of an evicted entry that no longer occurs in the buffer it was evicted from and deletes
all entries of that member from the other coupled buffers with del. Deletions do not evict, so
they cause no further synchronization.
"""

from collections.abc import Callable, Hashable, Iterable, Mapping
from typing import Any

from ocelescope_module_streaming.framework.buffer import Buffer

Members = Callable[[Any, Any], Iterable[Hashable]]
"""Maps an entry (key, value) of a buffer to the members (objects or object types) it belongs to."""


class CoupledRemoval:
    """Deletes the entries of evicted members from coupled buffers.

    Args:
        members: The coupled buffers, by name, each with the function giving the members of its
            entries.
    """

    def __init__(self, members: Mapping[str, tuple[Buffer[Any, Any], Members]]) -> None:
        self.members = dict(members)
        self._evicted: dict[str, list[tuple[Any, Any]]] = {}

    def evicted(self, name: str, entry: tuple[Any, Any] | None) -> None:
        """Records the entry that ins returned for buffer `name` (None if nothing was evicted)."""
        if entry is not None and name in self.members:
            self._evicted.setdefault(name, []).append(entry)

    def sync(self) -> int:
        """Deletes the entries of every member that left a buffer by eviction from the other
        coupled buffers.

        Returns:
            The number of deleted entries.
        """
        evicted, self._evicted = self._evicted, {}
        deleted = 0
        for name, entries in evicted.items():
            buffer, members_of = self.members[name]
            candidates = {member for key, value in entries for member in members_of(key, value)}
            gone = candidates - _present(buffer, members_of, candidates)
            if gone:
                deleted += self._delete(name, gone)
        return deleted

    def _delete(self, source: str, gone: set[Hashable]) -> int:
        deleted = 0
        for name, (buffer, members_of) in self.members.items():
            if name == source:
                continue
            doomed = [key for key, value in buffer.items() if not gone.isdisjoint(members_of(key, value))]
            for key in doomed:
                buffer.delete(key)
            deleted += len(doomed)
        return deleted


def _present(buffer: Buffer[Any, Any], members_of: Members, candidates: set[Hashable]) -> set[Hashable]:
    present: set[Hashable] = set()
    for key, value in buffer.items():
        present.update(member for member in members_of(key, value) if member in candidates)
        if len(present) == len(candidates):
            break
    return present
