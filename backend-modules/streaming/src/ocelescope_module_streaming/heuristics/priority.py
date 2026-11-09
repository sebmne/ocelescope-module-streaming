"""Object-type priority policies of Liss et al. 2025, combined with a cache policy.

The priority features follow `priority_policy_buffers.py` of the reference implementation
(loeseke/object-centric-streaming-discovery). Only the type-level features are available, since
buffers here mix object types; the reference allows the per-object features only with buffers
per object type.
"""

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.catalog import UnknownEntry, heuristics, register_heuristic
from ocelescope_module_streaming.framework import Context, Entry, EvictionMode, EvictionReason, Heuristic
from ocelescope_module_streaming.heuristics.ranking import normalize, normalize_map, owner_pair, owner_type
from ocelescope_module_streaming.stream import Event, O2OUpdate, ObjectRef, StreamItem

Order = Literal["min", "max"]
"""Whether types with the smallest (min) or largest (max) feature value are evicted first."""

FeatureName = Literal[
    "stride_per_type",
    "lifespan_per_type",
    "objects_per_event",
    "objects_per_type",
    "events_per_type",
    "custom",
]


class TypeFeature(ABC):
    """A per-type statistic, maintained from the stream with bounded memory."""

    @abstractmethod
    def update(self, item: StreamItem) -> None:
        """Processes a stream item."""

    @abstractmethod
    def values(self, order: Order) -> dict[str, float]:
        """The value per tracked type; the smallest value is evicted first."""


def _objects(item: StreamItem) -> list[ObjectRef]:
    if isinstance(item.x, Event):
        return list(item.x.objects)
    if isinstance(item.x, O2OUpdate):
        return [item.x.source, item.x.target]
    return []


def _seconds_value(seconds: float, order: Order) -> float:
    return seconds if order == "min" else 1 / (seconds + 1)


class _TrackedObjects(TypeFeature):
    """Tracks up to `max_objects` objects per type, replacing the oldest tracked one."""

    def __init__(self, max_objects: int = 5) -> None:
        self.max_objects = max_objects
        self.tracked: dict[str, dict[str, Any]] = {}

    def update(self, item: StreamItem) -> None:
        for obj in _objects(item):
            objects = self.tracked.setdefault(obj.type, {})
            if obj.id not in objects and len(objects) >= self.max_objects:
                del objects[next(iter(objects))]
            if obj.id in objects:
                self.seen(objects[obj.id], item.t)
            else:
                objects[obj.id] = self.first(item.t)

    @abstractmethod
    def first(self, time: datetime) -> Any: ...

    @abstractmethod
    def seen(self, state: Any, time: datetime) -> None: ...


class StridePerType(_TrackedObjects):
    """Mean time between consecutive events of the tracked objects of a type."""

    def __init__(self, max_objects: int = 5, window: int = 10) -> None:
        super().__init__(max_objects)
        self.window = window

    def first(self, time: datetime) -> Any:
        return {"last": time, "strides": deque(maxlen=self.window)}

    def seen(self, state: Any, time: datetime) -> None:
        state["strides"].append((time - state["last"]).total_seconds())
        state["last"] = time

    def values(self, order: Order) -> dict[str, float]:
        result = {}
        for object_type, objects in self.tracked.items():
            latest = max(state["last"] for state in objects.values())
            strides: list[float] = []
            for state in objects.values():
                strides.extend(state["strides"] or [(latest - state["last"]).total_seconds()])
            result[object_type] = _seconds_value(sum(strides) / len(strides), order)
        return result


class LifespanPerType(_TrackedObjects):
    """Mean time between the first and last event of the tracked objects of a type."""

    def first(self, time: datetime) -> Any:
        return [time, time]

    def seen(self, state: Any, time: datetime) -> None:
        state[1] = time

    def values(self, order: Order) -> dict[str, float]:
        result = {}
        for object_type, objects in self.tracked.items():
            spans = [(last - first).total_seconds() for first, last in objects.values()]
            result[object_type] = _seconds_value(sum(spans) / len(spans), order)
        return result


class ObjectsPerEvent(TypeFeature):
    """Mean number of objects of a type per event, over the last `window` events of the type."""

    def __init__(self, window: int = 10) -> None:
        self.counts: dict[str, deque[int]] = {}
        self.window = window

    def update(self, item: StreamItem) -> None:
        if not isinstance(item.x, Event):
            return
        per_type: dict[str, int] = {}
        for obj in item.x.objects:
            per_type[obj.type] = per_type.get(obj.type, 0) + 1
        for object_type, count in per_type.items():
            self.counts.setdefault(object_type, deque(maxlen=self.window)).append(count)

    def values(self, order: Order) -> dict[str, float]:
        means = {t: sum(counts) / len(counts) for t, counts in self.counts.items()}
        return means if order == "min" else {t: 1 / mean for t, mean in means.items()}


class ObjectsPerType(TypeFeature):
    """Number of distinct objects per type; all sets are reset when one reaches `window`."""

    def __init__(self, window: int = 1000) -> None:
        self.objects: dict[str, set[str]] = {}
        self.window = window

    def update(self, item: StreamItem) -> None:
        for obj in _objects(item):
            seen = self.objects.setdefault(obj.type, set())
            seen.add(obj.id)
            if len(seen) >= self.window:
                self.objects = {t: {next(iter(ids))} for t, ids in self.objects.items()}
                self.objects[obj.type] = {obj.id}

    def values(self, order: Order) -> dict[str, float]:
        return {t: len(ids) if order == "min" else 1 / len(ids) for t, ids in self.objects.items()}


class EventsPerType(TypeFeature):
    """Number of events per type; all counters are reset when one reaches `max_counter`."""

    def __init__(self, max_counter: int = 100_000) -> None:
        self.events: dict[str, int] = {}
        self.max_counter = max_counter

    def update(self, item: StreamItem) -> None:
        if not isinstance(item.x, Event):
            return
        for object_type in {obj.type for obj in item.x.objects}:
            count = self.events.get(object_type, 0) + 1
            if count >= self.max_counter:
                self.events = dict.fromkeys(self.events, 1)
                count = 1
            self.events[object_type] = count

    def values(self, order: Order) -> dict[str, float]:
        return {t: n if order == "min" else 1 / n for t, n in self.events.items()}


class CustomOrder(TypeFeature):
    """A fixed ranking of object types."""

    def __init__(self, types: Sequence[str]) -> None:
        self.types = list(types)

    def update(self, item: StreamItem) -> None:
        pass

    def values(self, order: Order) -> dict[str, float]:
        return {t: i if order == "min" else 1 / (i + 1) for i, t in enumerate(self.types)}


class PriorityParams(BaseModel):
    """Parameters of `Priority`."""

    model_config = ConfigDict(extra="forbid")

    cache: str = Field(default="fifo", description="Key of the cache policy combined with the priority.")
    cache_params: dict[str, Any] = Field(default_factory=dict, description="Parameters of the cache policy.")
    feature: FeatureName = Field(default="stride_per_type", description="The object-type characteristic.")
    order: Order = Field(default="min", description="Evict types with the smallest (min) or largest (max) value.")
    custom_order: list[str] = Field(default_factory=list, description="Object types for the custom feature.")


def _combine(rank: float, types: tuple[str | None, ...], priorities: dict[str, float]) -> float:
    """The combined rank of an entry about one object type, or about a type pair."""
    known = [priorities[t] for t in types if t is not None and t in priorities]
    if len(types) == 1:
        return rank + known[0] if known else 2 * rank
    if len(known) == 2:
        return 2 * rank + known[0] + known[1]
    if len(known) == 1:
        return 2 * rank + 2 * known[0]
    return 4 * rank


def make_feature(feature: FeatureName, custom_order: Sequence[str] = ()) -> TypeFeature:
    """Creates a type feature with the reference implementation's default windows."""
    match feature:
        case "stride_per_type":
            return StridePerType()
        case "lifespan_per_type":
            return LifespanPerType(max_objects=5)
        case "objects_per_event":
            return ObjectsPerEvent()
        case "objects_per_type":
            return ObjectsPerType()
        case "events_per_type":
            return EventsPerType()
        case "custom":
            return CustomOrder(custom_order)


@register_heuristic(
    key="priority",
    label="Cache + priority policy",
    description=(
        "Combines a cache policy with an object-type characteristic by summing their normalized ranks "
        "(Liss et al. 2025)."
    ),
    params=PriorityParams,
)
class Priority(Heuristic):
    """A cache policy combined with an object-type priority policy.

    Each candidate gets its min-max normalized cache rank r (0 = evicted first) plus the min-max
    normalized feature value p of its object type; candidates whose type has no value count
    their cache rank twice. Entries about a type pair (a, b), as in the TOTeM cardinality
    buffers, get 2r + p(a) + p(b), with 2p of the known type if only one is known and 4r if
    none is. The lowest sum is evicted.

    Args:
        cache: Key of the cache policy.
        cache_params: Parameters of the cache policy.
        feature: The object-type characteristic.
        order: Evict types with the smallest (min) or largest (max) value first.
        custom_order: Object types, for the custom feature.
    """

    modes = frozenset({EvictionMode.CAPACITY})

    def __init__(
        self,
        cache: str = "fifo",
        cache_params: dict[str, Any] | None = None,
        feature: FeatureName = "stride_per_type",
        order: Order = "min",
        custom_order: Sequence[str] = (),
    ) -> None:
        try:
            spec = heuristics.get(cache)
        except UnknownEntry as error:
            raise ValueError(str(error)) from error
        if EvictionMode.CAPACITY not in spec.modes or cache == "priority":
            raise ValueError(f"{spec.label} cannot be combined with a priority policy")
        self.cache = spec.factory(spec.params.model_validate(cache_params or {}))
        self.feature = make_feature(feature, custom_order)
        self.order: Order = order

    def scores(self, candidates: Sequence[tuple[Any, Entry[Any]]], ctx: Context) -> list[float]:
        cache_ranks = normalize([-score for score in self.cache.scores(candidates, ctx)])
        owners = [owner_pair(entry) or (owner_type(key, entry),) for key, entry in candidates]
        values = self.feature.values(self.order)
        present = {t: values[t] for types in owners for t in types if t is not None and t in values}
        priorities = normalize_map(present)
        return [-_combine(rank, types, priorities) for rank, types in zip(cache_ranks, owners, strict=True)]

    def score(self, key: Any, entry: Entry[Any], ctx: Context) -> float:
        return self.scores([(key, entry)], ctx)[0]

    def on_item(self, item: StreamItem, ctx: Context) -> None:
        self.feature.update(item)
        self.cache.on_item(item, ctx)

    def on_write(self, key: Any, entry: Entry[Any], ctx: Context) -> None:
        self.cache.on_write(key, entry, ctx)

    def on_evict(self, key: Any, entry: Entry[Any], ctx: Context, reason: EvictionReason) -> None:
        self.cache.on_evict(key, entry, ctx, reason)
