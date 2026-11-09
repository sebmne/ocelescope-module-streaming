"""Streaming discovery of DF2 graphs (Mühlmeyer et al. 2026; definitions.tex: def:df2)."""

from collections import Counter
from collections.abc import Mapping
from typing import Any

from ocelescope import OCEL
from ocelescope.ocel.constants.pm4py import ACTIVITY_COL, EID_COL, OID_COL, OTYPE_COL, TIMESTAMP_COL
from ocelescope.ocel.constants.tables import E2O_TABLE, EVENTS_TABLE, OBJECTS_TABLE
from ocelescope.util.sql import ident
from pydantic import BaseModel

from ocelescope_module_streaming.blocks import (
    ActivityTypeRelations,
    DFSnapshot,
    DirectlyFollowsCounters,
    DivergenceIndex,
    ObjectTracker,
    RelationsSnapshot,
)
from ocelescope_module_streaming.catalog import (
    ACTIVITIES_BOUND,
    ARCS_BOUND,
    ENDPOINTS_BOUND,
    BufferSpec,
    ElementScores,
    register_algorithm,
)
from ocelescope_module_streaming.framework import Buffer, BufferConfig, StreamingAlgorithm
from ocelescope_module_streaming.models import DF2Graph, build_df2
from ocelescope_module_streaming.stream import Event, StreamItem, StreamOptions

DF2_BUFFERS = (
    BufferSpec(
        "objects", "Objects", "The last activity of every open object. Grows with the number of objects in the log."
    ),
    BufferSpec("arcs", "Arcs", "Directly-follows relations per object type with their frequencies.", ARCS_BOUND),
    BufferSpec(
        "starts", "Start activities", "Start activities per object type with their frequencies.", ENDPOINTS_BOUND
    ),
    BufferSpec("ends", "End activities", "End activities of evicted objects with their frequencies.", ENDPOINTS_BOUND),
    BufferSpec("activities", "Activities", "Event counts per activity.", ACTIVITIES_BOUND),
    BufferSpec("relations", "Activity–type relations", "Event counts per activity and object type.", ENDPOINTS_BOUND),
    BufferSpec(
        "divergence",
        "Divergence index",
        "The first full object set per activity, type and typed object set. Grows with the number of distinct "
        "object combinations; entries of a pair are dropped once it diverges.",
    ),
    BufferSpec("divergent", "Divergent pairs", "Activity–type pairs found to diverge.", ENDPOINTS_BOUND),
)

EVENTS_ONLY = StreamOptions(events=True, object_to_object=False, attribute_updates=False)


def offline_df2(ocel: OCEL) -> DF2Graph:
    """Computes the DF2 graph of a complete log, ordering events as the replay does."""
    eid, oid, otype = ident(EID_COL), ident(OID_COL), ident(OTYPE_COL)
    rows = ocel.sql(
        f"SELECT e.{eid}, e.{ident(ACTIVITY_COL)}, r.{oid}, o.{otype} "
        f"FROM {ident(EVENTS_TABLE)} e JOIN {ident(E2O_TABLE)} r ON r.{eid} = e.{eid} "
        f"JOIN {ident(OBJECTS_TABLE)} o ON o.{oid} = r.{oid} "
        f"ORDER BY e.{ident(TIMESTAMP_COL)}, e.{eid}, r.{oid}"
    ).fetchall()

    events: list[tuple[str, dict[str, str]]] = []  # activity, object -> type
    current: Any = None
    for event_id, activity, object_id, object_type in rows:
        if event_id != current:
            events.append((str(activity), {}))
            current = event_id
        events[-1][1][str(object_id)] = str(object_type)

    arcs: Counter[tuple[str, str, str]] = Counter()
    starts: Counter[tuple[str, str]] = Counter()
    last: dict[tuple[str, str], str] = {}  # (object, type) -> activity
    full_sets: dict[tuple[str, str, frozenset[str]], set[frozenset[str]]] = {}
    for activity, objects in events:
        for object_id, object_type in objects.items():
            previous = last.get((object_id, object_type))
            if previous is None:
                starts[(activity, object_type)] += 1
            else:
                arcs[(previous, activity, object_type)] += 1
            last[(object_id, object_type)] = activity
        full = frozenset(objects)
        for object_type in set(objects.values()):
            typed = frozenset(o for o, t in objects.items() if t == object_type)
            full_sets.setdefault((activity, object_type, typed), set()).add(full)
    ends = Counter((activity, object_type) for (_, object_type), activity in last.items())
    divergent = {(a, t) for (a, t, _), sets in full_sets.items() if len(sets) > 1}
    snapshot = DFSnapshot(arcs=dict(arcs), starts=dict(starts), ends=dict(ends))
    return build_df2(snapshot, {activity for activity, _ in events}, divergent)


def offline_relations(ocel: OCEL) -> RelationsSnapshot:
    """Computes rel, con and def of a complete log directly from its tables."""
    eid, oid, otype, activity = ident(EID_COL), ident(OID_COL), ident(OTYPE_COL), ident(ACTIVITY_COL)
    rows = ocel.sql(
        f"WITH typed AS ("
        f"  SELECT e.{eid} AS eid, e.{activity} AS act, o.{otype} AS ot, count(DISTINCT r.{oid}) AS n "
        f"  FROM {ident(EVENTS_TABLE)} e JOIN {ident(E2O_TABLE)} r ON r.{eid} = e.{eid} "
        f"  JOIN {ident(OBJECTS_TABLE)} o ON o.{oid} = r.{oid} GROUP BY 1, 2, 3"
        f"), per_activity AS (SELECT act, count(DISTINCT eid) AS n FROM typed GROUP BY 1) "
        f"SELECT t.act, t.ot, count(*), max(t.n), any_value(p.n) FROM typed t "
        f"JOIN per_activity p ON p.act = t.act GROUP BY 1, 2"
    ).fetchall()
    return RelationsSnapshot(
        rel=frozenset((a, t) for a, t, _, _, _ in rows),
        con=frozenset((a, t) for a, t, _, most, _ in rows if most > 1),
        deficient=frozenset((a, t) for a, t, events, _, total in rows if events < total),
    )


def df2_elements(graph: DF2Graph) -> dict[str, set[Any]]:
    """The element sets of a DF2 graph, per kind."""
    return {
        "edges": {(edge.source, edge.target) for edge in graph.edges},
        "start activities": set(graph.start_activities),
        "end activities": set(graph.end_activities),
        "divergence": {(entry.activity, t) for entry in graph.divergence for t in entry.object_types},
    }


def compare_df2(streaming: DF2Graph, reference: DF2Graph) -> dict[str, ElementScores]:
    """Scores the edges, start and end activities and divergences against a reference."""
    found, expected = df2_elements(streaming), df2_elements(reference)
    return {kind: ElementScores.from_sets(found[kind], expected[kind]) for kind in expected}


class DF2Miner(StreamingAlgorithm[Any]):
    """Maintains everything the DF2 graph is built from.

    Blocks: `ObjectTracker` → `DirectlyFollowsCounters`, `ActivityTypeRelations` and
    `DivergenceIndex`. Subclasses turn the DF2 graph into other models.

    Args:
        params: The validated algorithm parameters.
        config: Buffer configurations by buffer name.
    """

    def __init__(self, params: BaseModel, config: Mapping[str, BufferConfig] | None = None) -> None:
        super().__init__(config)
        self._buffers = self.create_buffers(*(spec.name for spec in DF2_BUFFERS))
        objects, arcs, starts, ends, activities, relations, divergence, divergent = self._buffers
        self.tracker = ObjectTracker(objects)
        self.directly_follows = DirectlyFollowsCounters(self.tracker, arcs, starts, ends)
        self.relations = ActivityTypeRelations(activities, relations)
        self.divergence = DivergenceIndex(divergence, divergent)

    @property
    def buffers(self) -> tuple[Buffer[Any, Any], ...]:
        return self._buffers

    def update(self, item: StreamItem, position: int) -> None:
        if isinstance(item.x, Event) and item.x.relations:
            self.tracker.update(item.x, item.t)
            self.relations.update(item.x)
            self.divergence.update(item.x)

    def finish(self, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:
        self.tracker.finish(buffer, key, value)
        self.divergence.finish(buffer, key, value)

    def df2(self) -> DF2Graph:
        """Returns the current DF2 graph."""
        activities = (activity for activity, _ in self.relations.activities.items())
        return build_df2(self.directly_follows.snapshot(), activities, self.divergence.snapshot())

    def model(self) -> Any:
        return self.df2()


@register_algorithm(
    key="df2",
    label="DF2 graph",
    description=(
        "Divergence-free directly-follows graph (Mühlmeyer et al. 2026): directly-follows relations without "
        "those caused by divergent object types. The basis of the OCPT."
    ),
    model="DF2 graph",
    buffers=DF2_BUFFERS,
    stream=EVENTS_ONLY,
    offline=offline_df2,
    compare=compare_df2,
)
class StreamingDF2(DF2Miner):
    """Streaming DF2 graph discovery."""

    def model(self) -> DF2Graph:
        return self.df2()
