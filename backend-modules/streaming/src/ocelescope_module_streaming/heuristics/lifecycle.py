"""The lifecycle heuristic (paper, Definitions "Lifecycle Heuristic" and "Expected Lifetime").

For a buffer whose values carry an object type ot and a last activity a, a full buffer evicts the
object that exceeds its expected lifetime the most:

    H_LC(rho) = argmax_{o in keys(rho)} (|rho| - last(rho_o)) / life_rho(val_rho(o)).

The expected lifetime life(ot, a) in [T_int + 1, T_max] follows Mühlmeyer et al.: it is short if a
often ends lifecycles of type ot, judged by a histogram of the evictions in rho. The histogram is a
private buffer (U_type x U_act -> N) with capacity c_hist and LFU; every evict record (ot, a)
increments its count.

Private buffers: `last` holds (last(rho_o), ot, a) per buffered object, with the capacity of the
served buffer; `histogram` is a `Buffer` with its own LFU heuristic.
"""

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ocelescope_module_streaming.framework import (
    Buffer,
    Clock,
    Heuristic,
    PrivateBuffer,
    PrivateBufferInfo,
    register_heuristic,
)
from ocelescope_module_streaming.heuristics.cache import LFU


class LifecycleParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t_int: int = Field(
        default=200, ge=0, title="T_int", description="Inactivity (in items) an object can have in any case."
    )
    t_max: int = Field(default=2000, ge=1, title="T_max", description="The longest expected lifetime (in items).")
    c_hist: int = Field(default=100, ge=1, title="c_hist", description="Capacity of the end-activity histogram.")
    z: float = Field(default=1.0, gt=0, title="z", description="Width of the credible interval.")

    @model_validator(mode="after")
    def _ordered(self) -> "LifecycleParams":
        if self.t_int >= self.t_max:
            raise ValueError("T_int must be smaller than T_max")
        return self


def expected_lifetime(n_a: int, n: int, params: LifecycleParams) -> int:
    """life(ot, a) for n_a evictions of (ot, a) among n evictions of type ot (Definition "Expected
    Lifetime")."""
    pi = (n_a + 1) / (n + 2)
    variance = (n_a + 1) * (n - n_a + 1) / ((n + 2) ** 2 * (n + 3))
    kappa = max(0.0, pi - params.z * math.sqrt(variance))
    if kappa == 0:
        return params.t_max
    if kappa >= 0.9999:
        return params.t_int + 1
    return params.t_int + math.ceil((params.t_max - params.t_int) * 0.95 ** (kappa / (1 - kappa)))


def lifecycle_pair(value: Any) -> tuple[str, str]:
    """The pair (ot, a) of a buffered value: its attributes `object_type` and `activity`, or its
    first two components."""
    if hasattr(value, "object_type") and hasattr(value, "activity"):
        return str(value.object_type), str(value.activity)
    object_type, activity = value[0], value[1]
    return str(object_type), str(activity)


@register_heuristic
class Lifecycle(Heuristic[Any, Any]):
    name = "lifecycle"
    label = "Lifecycle"
    description = (
        "Evicts the object that exceeds its expected lifetime the most: argmax (|ρ| − last(ρ_o)) / life(ot, a). "
        "The lifetime is learned from a bounded histogram of evicted (object type, last activity) pairs."
    )
    Params = LifecycleParams
    needs_lifecycle_values = True
    private_info = (
        PrivateBufferInfo("last", "last(ρ_o) with the object type and last activity of each object"),
        PrivateBufferInfo(
            "histogram",
            "(object type, activity) → number of evictions ending there",
            capacity="c_hist",
            heuristic="lfu",
        ),
    )

    def __init__(self, capacity: int | None, clock: Clock, params: BaseModel | None = None) -> None:
        super().__init__(capacity, clock, params)
        assert isinstance(self.params, LifecycleParams)
        self.lifecycle_params: LifecycleParams = self.params
        # (last(rho_o), ot, a), ordered by last insertion for tie-breaking.
        self.last = PrivateBuffer[Any, tuple[int, str, str]]("last", capacity)
        histogram_capacity = self.lifecycle_params.c_hist
        self.histogram: Buffer[tuple[str, str], int] = Buffer(
            "histogram", histogram_capacity, LFU(histogram_capacity, clock), clock
        )

    def on_insert(self, key: Any, value: Any, position: int, new: bool) -> None:
        object_type, activity = lifecycle_pair(value)
        self.last.set(key, (position, object_type, activity), to_end=True)

    def on_evict(self, key: Any, value: Any, position: int) -> None:
        self.last.remove(key)
        pair = lifecycle_pair(value)
        self.histogram.ins(pair, self.histogram.get(pair, 0) + 1)

    def on_delete(self, key: Any, value: Any, position: int) -> None:
        # A deleted object was not forgotten because of its lifetime, so the histogram, which
        # learns from evictions, ignores it.
        self.last.remove(key)

    def life(self, object_type: str, activity: str) -> int:
        """life_rho(ot, a) for the current histogram."""
        n = sum(count for (ot, _), count in self.histogram.items() if ot == object_type)
        return expected_lifetime(self.histogram.get((object_type, activity), 0), n, self.lifecycle_params)

    def select(self, position: int) -> Any:
        totals: dict[str, int] = {}
        for (object_type, _), count in self.histogram.items():
            totals[object_type] = totals.get(object_type, 0) + count
        lifetimes: dict[tuple[str, str], int] = {}
        best, best_score = None, -1.0
        for key, (last, object_type, activity) in self.last.items():
            pair = (object_type, activity)
            life = lifetimes.get(pair)
            if life is None:
                n_a = self.histogram.get(pair, 0)
                life = lifetimes[pair] = expected_lifetime(n_a, totals.get(object_type, 0), self.lifecycle_params)
            score = (position - last) / life
            if score > best_score:
                best, best_score = key, score
        return best

    def private_buffers(self):
        return (self.last, self.histogram)
