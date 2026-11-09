"""Temporal object type models (TOTeM), following Liss et al. 2025 (`model_builder_totem.py`)."""

from collections.abc import Iterable, Mapping
from typing import Literal

from ocelescope import Resource
from ocelescope.visualization.default.graph import DIRECTED_ELK_GRAPH_LAYOUT, Graph, GraphEdge, GraphNode
from pydantic import BaseModel, Field

from ocelescope_module_streaming.blocks.observations import (
    EC_ONE,
    EC_ONE_MANY,
    EC_ZERO,
    EC_ZERO_MANY,
    EC_ZERO_ONE,
    EventCardinalityObservation,
    Lifespan,
    LogCardinalityObservation,
)
from ocelescope_module_streaming.stream import ObjectRef

TemporalRelation = Literal["during", "during_inv", "precedes", "precedes_inv", "parallel"]

TEMPORAL_RELATIONS: list[TemporalRelation] = ["during", "during_inv", "precedes", "precedes_inv", "parallel"]
LOG_CARDINALITIES = ["1", "0..1", "1..*", "0..*"]
EVENT_CARDINALITIES = [EC_ZERO, EC_ONE, EC_ZERO_ONE, EC_ONE_MANY, EC_ZERO_MANY]
"""Relations from most to least precise; a model edge carries the first one that holds."""

TypePair = tuple[str, str]


class TotemEdge(BaseModel):
    """The relations from one object type to another.

    Attributes:
        source: The source object type.
        target: The target object type.
        temporal: The most precise temporal relation, or None.
        log_cardinality: The most precise log cardinality, or None.
        event_cardinality: The most precise event cardinality, or None.
    """

    source: str
    target: str
    temporal: str | None = None
    log_cardinality: str | None = None
    event_cardinality: str | None = None


class Totem(Resource):
    """A temporal object type model.

    Attributes:
        object_types: The connected object types.
        edges: One edge per direction of every connected type pair.
        tau: The share of observations a relation must hold for.
    """

    label = "TOTeM"
    description = "A temporal object type model"

    object_types: list[str] = Field(default_factory=list)
    edges: list[TotemEdge] = Field(default_factory=list)
    tau: float = 1.0

    def visualize(self) -> Graph:
        nodes = [
            GraphNode(id=t, label=t, shape="rectangle", width=140, height=40, color="#ffffff")
            for t in self.object_types
        ]
        edges = [
            GraphEdge(
                source=edge.source,
                target=edge.target,
                end_arrow="triangle",
                label=f"{edge.temporal or '–'}: {edge.log_cardinality or '–'} ({edge.event_cardinality or '–'})",
            )
            for edge in self.edges
        ]
        return Graph(nodes=nodes, edges=edges, layout_config=DIRECTED_ELK_GRAPH_LAYOUT)


def _most_precise(scores: Mapping[str, float] | None, order: Iterable[str], tau: float) -> str | None:
    if scores is None:
        return None
    for relation in order:
        score = scores.get(relation)
        if score and score >= tau:
            return relation
    return None


def build_totem(
    lifespans: Mapping[ObjectRef, Lifespan],
    log_cardinality: Iterable[LogCardinalityObservation],
    event_cardinality: Iterable[EventCardinalityObservation],
    tau: float = 1.0,
) -> Totem:
    """Builds a TOTeM from the buffered observations.

    Connected types are those with a log- or event-cardinality observation of both. Event
    cardinalities are shares of the events of the source type; log cardinalities and temporal
    relations are shares of the objects and object pairs observed in log-cardinality entries.
    """
    log_cardinality = list(log_cardinality)
    event_cardinality = list(event_cardinality)

    connected: set[TypePair] = set()
    for observation in [*log_cardinality, *event_cardinality]:
        a, b = observation.types
        if b is not None:
            connected |= {(a, b), (b, a)}

    # Event cardinalities.
    events_of: dict[str, set[int]] = {}
    pair_events: dict[TypePair, dict[int, tuple[str, ...]]] = {}
    for observation in event_cardinality:
        a, b = observation.types
        events_of.setdefault(a, set()).add(observation.event)
        if b is not None:
            pair_events.setdefault((a, b), {})[observation.event] = observation.cardinalities
    ec_scores: dict[TypePair, dict[str, float] | None] = {}
    for a, b in connected:
        if a not in events_of:
            ec_scores[(a, b)] = None
            continue
        total = len(events_of[a])
        events = pair_events.get((a, b), {})
        zero = total - len(events)
        counts = {EC_ZERO: zero, EC_ONE: 0, EC_ZERO_ONE: zero, EC_ONE_MANY: 0, EC_ZERO_MANY: zero}
        for cardinalities in events.values():
            for cardinality in cardinalities:
                if cardinality != EC_ZERO:
                    counts[cardinality] += 1
        ec_scores[(a, b)] = {card: count / total for card, count in counts.items()}

    # Log cardinalities.
    pairs: dict[TypePair, set[tuple[str, str]]] = {}
    objects_of: dict[str, set[str]] = {}
    for observation in log_cardinality:
        (a, b), (id_a, id_b) = observation.types, observation.objects
        objects_of.setdefault(a, set()).add(id_a)
        if b is None or id_b is None:
            continue
        objects_of.setdefault(b, set()).add(id_b)
        pairs.setdefault((a, b), set()).add((id_a, id_b))
        pairs.setdefault((b, a), set()).add((id_b, id_a))
    lc_scores: dict[TypePair, dict[str, float] | None] = {}
    for a, b in connected:
        if (a, b) not in pairs:
            lc_scores[(a, b)] = None
            continue
        partners: dict[str, int] = {}
        for id_a, _ in pairs[(a, b)]:
            partners[id_a] = partners.get(id_a, 0) + 1
        counts = dict.fromkeys(LOG_CARDINALITIES, 0)
        for object_id in objects_of[a]:
            matches = partners.get(object_id, 0)
            for card in ("0..1", "0..*") if matches == 0 else LOG_CARDINALITIES if matches == 1 else ("1..*", "0..*"):
                counts[card] += 1
        lc_scores[(a, b)] = {card: count / len(objects_of[a]) for card, count in counts.items()}

    # Temporal relations over the object pairs of the log cardinalities.
    span: dict[tuple[str, str], Lifespan] = {(obj.type, obj.id): lifespan for obj, lifespan in lifespans.items()}
    tr_scores: dict[TypePair, dict[str, float]] = {}
    for a, b in connected:
        shares: dict[str, float] = dict.fromkeys(TEMPORAL_RELATIONS, 0.0)
        object_pairs = pairs.get((a, b), set())
        for id_a, id_b in object_pairs:
            first, second = span.get((a, id_a)), span.get((b, id_b))
            if first is None or second is None:
                continue
            for relation in _temporal_relations(first, second):
                shares[relation] += 1
        if object_pairs:
            shares = {relation: count / len(object_pairs) for relation, count in shares.items()}
        shares["parallel"] = 1.0
        tr_scores[(a, b)] = shares

    return Totem(
        object_types=sorted({t for pair in connected for t in pair}),
        edges=[
            TotemEdge(
                source=a,
                target=b,
                temporal=_most_precise(tr_scores[(a, b)], TEMPORAL_RELATIONS, tau),
                log_cardinality=_most_precise(lc_scores[(a, b)], LOG_CARDINALITIES, tau),
                event_cardinality=_most_precise(ec_scores[(a, b)], EVENT_CARDINALITIES, tau),
            )
            for a, b in sorted(connected)
        ],
        tau=tau,
    )


def _temporal_relations(a: Lifespan, b: Lifespan) -> list[TemporalRelation]:
    relations: list[TemporalRelation] = []
    if b.first <= a.first <= a.last <= b.last:
        relations.append("during")
    if a.first <= b.first <= b.last <= a.last:
        relations.append("during_inv")
    if a.first <= a.last <= b.first <= b.last or a.first < b.first <= a.last < b.last:
        relations.append("precedes")
    if b.first <= b.last <= a.first <= a.last or b.first < a.first <= b.last < a.last:
        relations.append("precedes_inv")
    return relations
