"""Heuristics for expiry mode (definitions.tex: sec:heuristics)."""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.catalog import register_heuristic
from ocelescope_module_streaming.framework import Context, Entry, EvictionMode, Heuristic


class MaxAgeParams(BaseModel):
    """Parameters of `MaxAge`."""

    model_config = ConfigDict(extra="forbid")

    age: int = Field(default=1000, ge=0, title="Age", description="Number of stream items a key may stay unwritten.")


@register_heuristic(
    key="max_age",
    label="Max age",
    description="Evicts a key once it has not been written for a fixed number of stream items.",
    params=MaxAgeParams,
)
class MaxAge(Heuristic):
    """Evicts a key `age` positions after its last write: δ(k) = l(k) + age.

    Args:
        age: The number of positions a key may stay unwritten.
    """

    modes: ClassVar[frozenset[EvictionMode]] = frozenset({EvictionMode.EXPIRY})

    def __init__(self, age: int = 1000) -> None:
        self.age = age

    def deadline(self, key: Any, entry: Entry[Any], ctx: Context) -> int | None:
        return entry.last + self.age
