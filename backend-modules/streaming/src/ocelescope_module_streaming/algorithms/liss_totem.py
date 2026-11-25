"""The streaming TOTeM of Liss et al. (2025), Section 5.1 "TOTeM Buffers".

Three buffers:
    lifespans          object -> (object type, last activity, first seen, last seen)
    log_cardinality    row id -> (undirected type pair, object pair)
    event_cardinality  row id -> (directed type pair, event, allowed event cardinalities)

Events update the lifespans of their objects: a new object gets its timestamp as first and last,
a buffered one only a new last. Events and O2O updates insert one log-cardinality row per pair of
their objects of different types. Events insert one event-cardinality row per directed pair of
their object types, holding the cardinalities the event allows: {1..*, 0..*} if it has several
objects of the target type, {1, 0..1, 1..*, 0..*} if it has one. An event with a single object type
inserts one row (ot, None) with {0, 0..1, 0..*}, so that events without any other type count
towards the cardinality 0, which the event cardinality of Liss et al. requires.

Extension: the lifespan entries also hold the last activity of the object. The model ignores it,
but it lets the lifecycle heuristic serve the lifespan buffer.

The model, for each pair (a, b) of connected types (types related by a row), with threshold tau:
    event cardinality   the most precise cardinality allowed by at least tau of the buffered
                        events of type a (events without type b allow 0, 0..1 and 0..*);
    log cardinality     the most precise cardinality that holds for at least tau of the buffered
                        objects of type a, counting their buffered partners of type b;
    temporal relation   the most precise relation that holds for at least tau of the buffered
                        object pairs whose lifespans are buffered; parallel always holds.

Rows have fresh keys (position, index), so full row buffers forget old behaviour. The optional
buffer synchronization of Liss et al. is not represented, because the framework only inserts.
"""

from collections.abc import Iterable, Mapping
from itertools import combinations
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.framework import BufferSpec, StreamingAlgorithm, register_algorithm
from ocelescope_module_streaming.models import (
    EVENT_CARDINALITIES,
    LOG_CARDINALITIES,
    TEMPORAL_RELATIONS,
    Totem,
    TotemEdge,
)
from ocelescope_module_streaming.stream import Event, O2OUpdate, StreamItem, StreamOptions, Timestamp, tobj


class Lifespan(NamedTuple):
    """An entry of the lifespan (temporal-relation) buffer."""

    object_type: str
    activity: str
    first: Timestamp
    last: Timestamp


class LogCardinalityRow(NamedTuple):
    """Two related objects of different types, with their types in sorted order."""

    types: tuple[str, str]
    objects: tuple[str, str]


class EventCardinalityRow(NamedTuple):
    """The cardinalities an event allows from its type `source` to type `target` (None: to any type
    the event lacks)."""

    source: str
    target: str | None
    event: int
    cardinalities: frozenset[str]


MANY = frozenset({"1..*", "0..*"})
ONE = frozenset({"1", "0..1", "1..*", "0..*"})
NONE = frozenset({"0", "0..1", "0..*"})


class TotemParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tau: float = Field(
        default=1.0, ge=0, le=1, title="τ", description="The share of observations a relation must hold for."
    )


@register_algorithm
class LissTotem(StreamingAlgorithm[Totem]):
    key = "liss_totem"
    label = "TOTeM (Liss et al.)"
    description = (
        "The streaming TOTeM of Liss et al. (2025): lifespans of objects, and rows for related object pairs and "
        "for the event cardinalities of each event. The model computes temporal relations and cardinalities "
        "between object types from the buffered entries."
    )
    model_label = "TOTeM"
    stream = StreamOptions(events=True, o2o_updates=True, attribute_updates=False)
    Params = TotemParams
    buffer_specs = (
        BufferSpec(
            "lifespans",
            "Temporal-relation buffer",
            "The first and last timestamp of each object (and its last activity).",
            key="object",
            value="(object type, last activity, first, last)",
            lifecycle_values=True,
            default_capacity=500,
            holds_model=True,
        ),
        BufferSpec(
            "log_cardinality",
            "Log-cardinality buffer",
            "One row per pair of related objects of different types, from events and O2O updates.",
            key="row (position, index)",
            value="(type pair, object pair)",
            default_capacity=1000,
            holds_model=True,
        ),
        BufferSpec(
            "event_cardinality",
            "Event-cardinality buffer",
            "One row per event and directed pair of its object types, with the cardinalities the event allows.",
            key="row (position, index)",
            value="(source type, target type, event, cardinalities)",
            default_capacity=1000,
            holds_model=True,
        ),
    )

    def upd(self, item: StreamItem) -> None:
        if not isinstance(item.x, Event | O2OUpdate):
            return
        position = self.clock.position
        typed = tobj(item)
        if isinstance(item.x, Event):
            lifespans = self.buffers["lifespans"]
            for o in typed:
                before: Lifespan | None = lifespans.get(o.id)
                first = item.t if before is None else before.first
                lifespans.ins(o.id, Lifespan(o.type, item.x.activity, first, item.t))
        log_rows = self.buffers["log_cardinality"]
        index = 0
        for x, y in combinations(typed, 2):
            if x.type == y.type:
                continue
            (ta, oa), (tb, ob) = sorted(((x.type, x.id), (y.type, y.id)))
            log_rows.ins((position, index), LogCardinalityRow((ta, tb), (oa, ob)))
            index += 1
        if isinstance(item.x, Event):
            self._insert_event_cardinalities(position, [o.type for o in typed])

    def _insert_event_cardinalities(self, position: int, types: list[str]) -> None:
        rows = self.buffers["event_cardinality"]
        counts: dict[str, int] = {}
        for t in types:
            counts[t] = counts.get(t, 0) + 1
        if len(counts) == 1:
            (only,) = counts
            rows.ins((position, 0), EventCardinalityRow(only, None, position, NONE))
            return
        index = 0
        for source in counts:
            for target, n in counts.items():
                if target != source:
                    rows.ins((position, index), EventCardinalityRow(source, target, position, MANY if n > 1 else ONE))
                    index += 1

    def emit(self) -> Totem:
        assert isinstance(self.params, TotemParams)
        return build_totem(
            dict(self.buffers["lifespans"].items()),
            self.buffers["log_cardinality"].values(),
            self.buffers["event_cardinality"].values(),
            self.params.tau,
        )


def build_totem(
    lifespans: Mapping[str, Lifespan],
    log_rows: Iterable[LogCardinalityRow],
    event_rows: Iterable[EventCardinalityRow],
    tau: float,
) -> Totem:
    """Computes a TOTeM from buffered lifespans and rows."""
    log_rows, event_rows = list(log_rows), list(event_rows)
    connected: set[tuple[str, str]] = set()
    partners: dict[tuple[str, str], dict[str, set[str]]] = {}  # (a, b) -> object of a -> partners of b
    objects_of: dict[str, set[str]] = {}
    for obj, span in lifespans.items():
        objects_of.setdefault(span.object_type, set()).add(obj)
    for row in log_rows:
        (ta, tb), (oa, ob) = row.types, row.objects
        connected |= {(ta, tb), (tb, ta)}
        objects_of.setdefault(ta, set()).add(oa)
        objects_of.setdefault(tb, set()).add(ob)
        partners.setdefault((ta, tb), {}).setdefault(oa, set()).add(ob)
        partners.setdefault((tb, ta), {}).setdefault(ob, set()).add(oa)
    events_of: dict[str, set[int]] = {}
    allowed: dict[tuple[str, str], dict[int, frozenset[str]]] = {}
    for row in event_rows:
        events_of.setdefault(row.source, set()).add(row.event)
        if row.target is not None:
            connected.add((row.source, row.target))
            allowed.setdefault((row.source, row.target), {})[row.event] = row.cardinalities

    def most_precise(holds: Mapping[str, int], total: int, order: Iterable[str]) -> str | None:
        if total == 0:
            return None
        return next((r for r in order if holds.get(r, 0) / total >= tau), None)

    edges: list[TotemEdge] = []
    for a, b in sorted(connected):
        # Event cardinality: over the buffered events of type a.
        events = events_of.get(a, set())
        with_b = allowed.get((a, b), {})
        ec: dict[str, int] = {}
        for event in events:
            for cardinality in with_b.get(event, NONE):
                ec[cardinality] = ec.get(cardinality, 0) + 1
        # Log cardinality: over the buffered objects of type a.
        lc: dict[str, int] = {}
        pair_partners = partners.get((a, b), {})
        for obj in objects_of.get(a, set()):
            n = len(pair_partners.get(obj, ()))
            for cardinality in ("0..1", "0..*") if n == 0 else LOG_CARDINALITIES if n == 1 else MANY:
                lc[cardinality] = lc.get(cardinality, 0) + 1
        # Temporal relation: over the related object pairs with buffered lifespans.
        tr: dict[str, int] = {}
        pairs = 0
        for obj, others in pair_partners.items():
            for other in others:
                first, second = lifespans.get(obj), lifespans.get(other)
                if first is None or second is None:
                    continue
                pairs += 1
                for relation in temporal_relations(first, second):
                    tr[relation] = tr.get(relation, 0) + 1
        temporal = most_precise(tr, pairs, TEMPORAL_RELATIONS) if pairs else "parallel"
        edges.append(
            TotemEdge(
                source=a,
                target=b,
                temporal=temporal,
                log_cardinality=most_precise(lc, len(objects_of.get(a, ())), LOG_CARDINALITIES),
                event_cardinality=most_precise(ec, len(events), EVENT_CARDINALITIES),
            )
        )
    return Totem(object_types=sorted({t for pair in connected for t in pair}), edges=edges, tau=tau)


def temporal_relations(a: Lifespan, b: Lifespan) -> list[str]:
    """The temporal relations from the lifespan of a to that of b; parallel always holds."""
    relations: list[str] = []
    if b.first <= a.first and a.last <= b.last:  # type: ignore[operator]
        relations.append("during")
    if a.first <= b.first and b.last <= a.last:  # type: ignore[operator]
        relations.append("during_inv")
    if a.last <= b.first or a.first < b.first <= a.last < b.last:  # type: ignore[operator]
        relations.append("precedes")
    if b.last <= a.first or b.first < a.first <= b.last < a.last:  # type: ignore[operator]
        relations.append("precedes_inv")
    relations.append("parallel")
    return relations
