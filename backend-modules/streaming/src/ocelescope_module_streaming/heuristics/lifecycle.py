"""The lifecycle heuristic of Mühlmeyer et al. 2026 (definitions.tex: def:lifecycle)."""

import math
from typing import Any, ClassVar, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ocelescope_module_streaming.catalog import register_heuristic
from ocelescope_module_streaming.framework import Context, Entry, EvictionMode, EvictionReason, Heuristic
from ocelescope_module_streaming.stream import ObjectRef

Z = 1.0
"""Confidence multiplier of the credible-interval lower bound."""

BETA = 0.95
"""Base of the decay that maps confidence to an eviction age."""


class HasActivity(Protocol):
    """A buffered value that knows the last activity of its object, e.g. `blocks.LastSeen`."""

    @property
    def activity(self) -> str: ...


def confidence(k: int, n: int) -> float:
    """Lower bound of the Beta-binomial credible interval that an activity ends a lifecycle.

    Args:
        k: Lifecycles of the type that ended with the activity.
        n: Lifecycles of the type observed in total.
    """
    if n == 0:
        return 0.0
    mu = (k + 1) / (n + 2)
    sigma = math.sqrt((k + 1) * (n - k + 1) / ((n + 2) ** 2 * (n + 3)))
    return min(1.0, max(0.0, mu - Z * sigma))


def eviction_age(c: float, t_hint: int, t_max: int) -> int:
    """The number of positions an object may stay inactive, given the confidence `c`."""
    if c <= 0:
        return t_max
    if c >= 0.9999:
        return t_hint + 1
    return t_hint + math.ceil((t_max - t_hint) * BETA ** (c / (1 - c)))


class LifecycleParams(BaseModel):
    """Parameters of `Lifecycle`."""

    model_config = ConfigDict(extra="forbid")

    t_hint: int = Field(default=200, ge=0, description="Inactivity during which an object is always kept.")
    t_max: int = Field(default=2000, ge=1, description="Inactivity after which an object is always evicted.")

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.t_hint >= self.t_max:
            raise ValueError("t_hint must be smaller than t_max")
        return self


@register_heuristic(
    key="lifecycle",
    label="Lifecycle",
    description=(
        "Evicts an object between t_hint and t_max stream items after its last event, earlier the more "
        "often its last activity ended the lifecycles of its type (Mühlmeyer et al. 2026)."
    ),
    params=LifecycleParams,
)
class Lifecycle(Heuristic):
    """Schedules each object's eviction from an end-activity histogram.

    For an object buffer keyed by `ObjectRef` whose values know their last activity. The
    histogram counts objects evicted for capacity and objects that expired after at least
    `t_max` positions of inactivity.

    Args:
        t_hint: Inactivity during which an object is always kept.
        t_max: Inactivity after which an object is always evicted.
    """

    modes: ClassVar[frozenset[EvictionMode]] = frozenset({EvictionMode.EXPIRY})

    def __init__(self, t_hint: int = 200, t_max: int = 2000) -> None:
        LifecycleParams(t_hint=t_hint, t_max=t_max)
        self.t_hint = t_hint
        self.t_max = t_max
        self.ends: dict[tuple[str, str], int] = {}  # κ: (activity, type) -> lifecycles ended
        self.totals: dict[str, int] = {}  # ν: type -> lifecycles observed

    def age(self, activity: str, object_type: str) -> int:
        """The eviction age α(a, t) under the current histogram."""
        k = self.ends.get((activity, object_type), 0)
        n = self.totals.get(object_type, 0)
        return eviction_age(confidence(k, n), self.t_hint, self.t_max)

    def deadline(self, key: Any, entry: Entry[Any], ctx: Context) -> int | None:
        obj: ObjectRef = key
        value: HasActivity = entry.value
        return entry.last + self.age(value.activity, obj.type)

    def on_evict(self, key: Any, entry: Entry[Any], ctx: Context, reason: EvictionReason) -> None:
        dead = reason is EvictionReason.EXPIRED and ctx.position - entry.last >= self.t_max
        if reason is EvictionReason.CAPACITY or dead:
            obj: ObjectRef = key
            value: HasActivity = entry.value
            pair = (value.activity, obj.type)
            self.ends[pair] = self.ends.get(pair, 0) + 1
            self.totals[obj.type] = self.totals.get(obj.type, 0) + 1
