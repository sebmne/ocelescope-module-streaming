"""Activity–type relations (definitions.tex: def:relations)."""

from dataclasses import dataclass

from ocelescope_module_streaming.blocks.directly_follows import increment
from ocelescope_module_streaming.framework import Buffer
from ocelescope_module_streaming.stream import Event

Relation = tuple[str, str]
"""An activity and an object type."""


@dataclass(frozen=True, slots=True)
class RelationCounts:
    """Event counts behind an activity–type relation.

    Attributes:
        events: Events of the activity with at least one object of the type, N(a, t).
        converging: Events of the activity with more than one object of the type, N>1(a, t).
    """

    events: int
    converging: int


@dataclass(frozen=True, slots=True)
class RelationsSnapshot:
    """The activity–type relations rel, con and def."""

    rel: frozenset[Relation]
    con: frozenset[Relation]
    deficient: frozenset[Relation]


class ActivityTypeRelations:
    """Counts how often activities occur with objects of each type.

    Args:
        activities: Buffer of event counts per activity, N(a).
        relations: Buffer of `RelationCounts` per (activity, type).
    """

    def __init__(self, activities: Buffer[str, int], relations: Buffer[Relation, RelationCounts]) -> None:
        self.activities = activities
        self.relations = relations

    def update(self, event: Event) -> None:
        """Processes an event."""
        increment(self.activities, event.activity)
        per_type: dict[str, int] = {}
        for obj in set(event.objects):
            per_type[obj.type] = per_type.get(obj.type, 0) + 1
        for object_type, count in per_type.items():
            key = (event.activity, object_type)
            counts = self.relations.get(key) or RelationCounts(0, 0)
            self.relations.put(key, RelationCounts(counts.events + 1, counts.converging + (count > 1)))

    def snapshot(self) -> RelationsSnapshot:
        """Returns rel, con and def from the current counts."""
        rel, con, deficient = set[Relation](), set[Relation](), set[Relation]()
        for (activity, object_type), counts in self.relations.items():
            rel.add((activity, object_type))
            if counts.converging:
                con.add((activity, object_type))
            if counts.events < (self.activities.get(activity) or 0):
                deficient.add((activity, object_type))
        return RelationsSnapshot(frozenset(rel), frozenset(con), frozenset(deficient))
