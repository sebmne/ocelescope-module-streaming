"""The streaming OC-DFG and TOTeM discovery of Liss et al. 2025.

Model buffers hold observations, so the model is whatever the buffers currently hold. Buffers
can optionally be synchronized by object type after each item (coupled removal).
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from ocelescope import OCEL, DirectlyFollowsGraph
from ocelescope.discovery import ocdfg_miner
from ocelescope.ocel.constants.pm4py import (
    EID_COL,
    O2O_SOURCE_ID,
    O2O_TARGET_ID,
    OID_COL,
    OTYPE_COL,
    TIMESTAMP_COL,
)
from ocelescope.ocel.constants.tables import E2O_TABLE, EVENTS_TABLE, O2O_TABLE, OBJECTS_TABLE
from ocelescope.resource.default.dfg import DFGActivity, DFGEdge, DFGObject
from ocelescope.util.sql import ident
from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.algorithms.ocdfg import compare_ocdfgs
from ocelescope_module_streaming.blocks import (
    ArcObservation,
    DirectlyFollowsLog,
    Lifespan,
    ObjectInteractions,
    ObjectTracker,
    coupled_removal,
)
from ocelescope_module_streaming.blocks.observations import (
    EC_ONE,
    EC_ONE_MANY,
    EC_ZERO,
    EC_ZERO_MANY,
    EC_ZERO_ONE,
)
from ocelescope_module_streaming.catalog import BufferSpec, ElementScores, register_algorithm
from ocelescope_module_streaming.framework import Buffer, BufferConfig, StreamingAlgorithm
from ocelescope_module_streaming.models import Totem, build_totem
from ocelescope_module_streaming.models.totem import (
    EVENT_CARDINALITIES,
    LOG_CARDINALITIES,
    TEMPORAL_RELATIONS,
    TotemEdge,
    _temporal_relations,
)
from ocelescope_module_streaming.stream import Event, O2OUpdate, StreamItem, StreamOptions


class LissParams(BaseModel):
    """Parameters of the Liss et al. algorithms."""

    model_config = ConfigDict(extra="forbid")

    coupled_removal: bool = Field(
        default=False, description="After each item, keep only entries of object types present in every buffer."
    )


class TotemParams(LissParams):
    """Parameters of `LissTotem`."""

    tau: float = Field(default=1.0, ge=0, le=1, description="Share of observations a relation must hold for.")


# OC-DFG


def build_liss_ocdfg(arcs: Iterable[ArcObservation]) -> DirectlyFollowsGraph:
    """Builds the OC-DFG of an arc observation log.

    Arc frequencies are numbers of observations. Start activities come from observations without
    a source; end activities are activities without outgoing arcs of their type.
    """
    inner: Counter[tuple[str, str, str]] = Counter()
    starts: Counter[tuple[str, str]] = Counter()
    targets: dict[str, set[str]] = {}
    for arc in arcs:
        targets.setdefault(arc.obj.type, set()).add(arc.target)
        if arc.source is None:
            starts[(arc.target, arc.obj.type)] += 1
        else:
            inner[(arc.source, arc.target, arc.obj.type)] += 1
    sources = {(source, object_type) for source, _, object_type in inner}
    ends = [(a, t) for t, activities in targets.items() for a in sorted(activities) if (a, t) not in sources]

    def edge(object_type: str, source: str | None, target: str | None, count: int) -> DFGEdge:
        return DFGEdge(object_type=object_type, source=source, target=target, count=count, object_count=count)

    edges = [
        *(edge(t, a, b, n) for (a, b, t), n in sorted(inner.items())),
        *(edge(t, None, a, n) for (a, t), n in sorted(starts.items())),
        *(edge(t, a, None, 1) for a, t in ends),
    ]
    activities = sorted({name for e in edges for name in (e.source, e.target) if name})
    return DirectlyFollowsGraph(
        activities=[DFGActivity(name=a) for a in activities],
        object_types=[DFGObject(name=t) for t in sorted(targets)],
        edges=edges,
    )


def compare_liss_ocdfgs(streaming: DirectlyFollowsGraph, reference: DirectlyFollowsGraph) -> dict[str, ElementScores]:
    """Scores arcs and start activities; end activities are inferred differently by design."""
    scores = compare_ocdfgs(streaming, reference)
    return {kind: scores[kind] for kind in ("arcs", "start activities")}


@register_algorithm(
    key="liss_ocdfg",
    label="Streaming OC-DFG (Liss et al.)",
    description="OC-DFG from a buffer of arc observations; the model is the buffer content (Liss et al. 2025).",
    buffers=(
        BufferSpec(
            "objects",
            "Objects",
            "The last activity and time of every open object. Grows with the number of objects in the log.",
        ),
        BufferSpec(
            "arcs",
            "Arc observations",
            "One entry per object and directly-follows step; the model is computed from these entries. "
            "Grows with the length of the stream.",
        ),
    ),
    stream=StreamOptions(events=True, object_to_object=False, attribute_updates=False),
    offline=ocdfg_miner,
    compare=compare_liss_ocdfgs,
    params=LissParams,
)
class LissOCDFG(StreamingAlgorithm[DirectlyFollowsGraph]):
    """Streaming OC-DFG discovery of Liss et al. 2025.

    Args:
        params: The validated `LissParams`.
        config: Buffer configurations by buffer name.
    """

    def __init__(self, params: BaseModel, config: Mapping[str, BufferConfig] | None = None) -> None:
        super().__init__(config)
        assert isinstance(params, LissParams)
        self.params = params
        self.objects, self.arcs = self.create_buffers("objects", "arcs")
        self.tracker = ObjectTracker(self.objects)
        self.log = DirectlyFollowsLog(self.tracker, self.arcs)

    @property
    def buffers(self) -> tuple[Buffer[Any, Any], ...]:
        return (self.objects, self.arcs)

    def update(self, item: StreamItem, position: int) -> None:
        if isinstance(item.x, Event):
            self.tracker.update(item.x, item.t)

    def after_evictions(self, position: int) -> None:
        if self.params.coupled_removal:
            coupled_removal([(self.objects, lambda key, _: [key.type]), (self.arcs, lambda _, arc: [arc.obj.type])])

    def model(self) -> DirectlyFollowsGraph:
        return build_liss_ocdfg(arc for _, arc in self.arcs.items())


# TOTeM


def offline_totem(ocel: OCEL, params: TotemParams | None = None) -> Totem:
    """Discovers the TOTeM of a complete log (port of Liss et al.'s `discover_totem_offline`).

    Objects are related if they share an event or an O2O relation whose source object has an
    event, as in the replay.
    """
    tau = (params or TotemParams()).tau
    eid, oid, otype = ident(EID_COL), ident(OID_COL), ident(OTYPE_COL)
    rows = ocel.sql(
        f"SELECT e.{eid}, e.{ident(TIMESTAMP_COL)}, r.{oid}, o.{otype} "
        f"FROM {ident(EVENTS_TABLE)} e JOIN {ident(E2O_TABLE)} r ON r.{eid} = e.{eid} "
        f"JOIN {ident(OBJECTS_TABLE)} o ON o.{oid} = r.{oid} ORDER BY e.{ident(TIMESTAMP_COL)}, e.{eid}"
    ).fetchall()
    events: dict[Any, tuple[datetime, dict[str, set[str]]]] = {}
    for event_id, time, object_id, object_type in rows:
        events.setdefault(event_id, (time, {}))[1].setdefault(str(object_type), set()).add(str(object_id))

    types: set[str] = set()
    type_of: dict[str, str] = {}
    first: dict[str, datetime] = {}
    last: dict[str, datetime] = {}
    partners: dict[str, dict[str, set[str]]] = {}
    connected: set[frozenset[str]] = set()
    event_cards: dict[tuple[str, str], Counter[str]] = {}
    for time, by_type in events.values():
        types.update(by_type)
        for object_type, ids in by_type.items():
            for object_id in ids:
                type_of[object_id] = object_type
                first[object_id] = min(first.get(object_id, time), time)
                last[object_id] = max(last.get(object_id, time), time)
                for other_type, others in by_type.items():
                    if other_type != object_type:
                        partners.setdefault(object_id, {}).setdefault(other_type, set()).update(others)
        for a in by_type:
            for b in by_type:
                if a != b:
                    connected.add(frozenset((a, b)))
    for _, by_type in events.values():
        for source_type in by_type:
            for target_type in types:
                counts = event_cards.setdefault((source_type, target_type), Counter())
                counts["total"] += 1
                n = len(by_type.get(target_type, ()))
                cards = (
                    (EC_ZERO, EC_ZERO_ONE, EC_ZERO_MANY)
                    if n == 0
                    else (EC_ONE, EC_ZERO_ONE, EC_ONE_MANY, EC_ZERO_MANY)
                    if n == 1
                    else (EC_ONE_MANY, EC_ZERO_MANY)
                )
                counts.update(cards)

    o2o_source, o2o_target = ident(O2O_SOURCE_ID), ident(O2O_TARGET_ID)
    for source_id, target_id in ocel.sql(f"SELECT {o2o_source}, {o2o_target} FROM {ident(O2O_TABLE)}").fetchall():
        a, b = type_of.get(str(source_id)), type_of.get(str(target_id))
        if a is None or b is None or a == b:
            continue
        partners.setdefault(str(source_id), {}).setdefault(b, set()).add(str(target_id))
        partners.setdefault(str(target_id), {}).setdefault(a, set()).add(str(source_id))
        connected.add(frozenset((a, b)))

    objects_of: dict[str, list[str]] = {}
    for object_id, object_type in type_of.items():
        objects_of.setdefault(object_type, []).append(object_id)

    def relations(a: str, b: str) -> TotemEdge:
        lc: Counter[str] = Counter()
        tr: Counter[str] = Counter()
        for object_id in objects_of.get(a, []):
            others = partners.get(object_id, {}).get(b, set())
            lc["total"] += 1
            n = len(others)
            lc.update(("0..1", "0..*") if n == 0 else LOG_CARDINALITIES if n == 1 else ("1..*", "0..*"))
            for other in others:
                tr["total"] += 1
                tr["parallel"] += 1
                tr.update(
                    _temporal_relations(
                        Lifespan(first[object_id], last[object_id]), Lifespan(first[other], last[other])
                    )
                )
        ec = event_cards.get((a, b), Counter())
        return TotemEdge(
            source=a,
            target=b,
            temporal=_first(tr, TEMPORAL_RELATIONS, tau),
            log_cardinality=_first(lc, LOG_CARDINALITIES, tau),
            event_cardinality=_first(ec, EVENT_CARDINALITIES, tau),
        )

    pairs = sorted((a, b) for pair in connected for a in pair for b in pair if a != b)
    return Totem(
        object_types=sorted({t for pair in connected for t in pair}),
        edges=[relations(a, b) for a, b in pairs],
        tau=tau,
    )


def _first(counts: Counter[str], order: Iterable[str], tau: float) -> str | None:
    total = counts["total"]
    if total == 0:
        return None
    return next((relation for relation in order if counts[relation] and counts[relation] / total >= tau), None)


def totem_elements(totem: Totem) -> dict[str, set[Any]]:
    """The element sets of a TOTeM, per kind."""
    return {
        "object types": set(totem.object_types),
        "edges": {(e.source, e.target) for e in totem.edges},
        "temporal relations": {(e.source, e.target, e.temporal) for e in totem.edges},
        "log cardinalities": {(e.source, e.target, e.log_cardinality) for e in totem.edges},
        "event cardinalities": {(e.source, e.target, e.event_cardinality) for e in totem.edges},
    }


def compare_totems(streaming: Totem, reference: Totem) -> dict[str, ElementScores]:
    """Scores object types, edges and the relations on edges against a reference."""
    found, expected = totem_elements(streaming), totem_elements(reference)
    return {kind: ElementScores.from_sets(found[kind], expected[kind]) for kind in expected}


@register_algorithm(
    key="liss_totem",
    label="Streaming TOTeM (Liss et al.)",
    description="Temporal object type model from buffers of lifespans and cardinality observations (Liss et al. 2025).",
    buffers=(
        BufferSpec("lifespans", "Lifespans", "First and last event time per object. Grows with the number of objects."),
        BufferSpec(
            "log_cardinality",
            "Log cardinalities",
            "Object pairs of different types related by an item. Grows with the length of the stream.",
        ),
        BufferSpec(
            "event_cardinality",
            "Event cardinalities",
            "Cardinalities an event allows per pair of its object types. Grows with the length of the stream.",
        ),
    ),
    stream=StreamOptions(events=True, object_to_object=True, attribute_updates=False),
    offline=offline_totem,
    compare=compare_totems,
    params=TotemParams,
)
class LissTotem(StreamingAlgorithm[Totem]):
    """Streaming TOTeM discovery of Liss et al. 2025.

    Args:
        params: The validated `TotemParams`.
        config: Buffer configurations by buffer name.
    """

    def __init__(self, params: BaseModel, config: Mapping[str, BufferConfig] | None = None) -> None:
        super().__init__(config)
        assert isinstance(params, TotemParams)
        self.params = params
        self.lifespans, self.log_cardinality, self.event_cardinality = self.create_buffers(
            "lifespans", "log_cardinality", "event_cardinality"
        )
        self.interactions = ObjectInteractions(self.lifespans, self.log_cardinality, self.event_cardinality)

    @property
    def buffers(self) -> tuple[Buffer[Any, Any], ...]:
        return (self.lifespans, self.log_cardinality, self.event_cardinality)

    def update(self, item: StreamItem, position: int) -> None:
        if isinstance(item.x, Event | O2OUpdate):
            self.interactions.update(item.x, item.t)

    def after_evictions(self, position: int) -> None:
        if self.params.coupled_removal:

            def pair(_: Any, value: Any) -> list[str]:
                return [t for t in value.types if t is not None]

            coupled_removal(
                [
                    (self.lifespans, lambda key, _: [key.type]),
                    (self.log_cardinality, pair),
                    (self.event_cardinality, pair),
                ]
            )

    def model(self) -> Totem:
        return build_totem(
            dict(self.lifespans.items()),
            (value for _, value in self.log_cardinality.items()),
            (value for _, value in self.event_cardinality.items()),
            self.params.tau,
        )
