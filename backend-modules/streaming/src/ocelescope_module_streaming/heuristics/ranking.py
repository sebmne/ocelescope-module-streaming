"""Helpers for rank-based heuristics."""

from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

from ocelescope_module_streaming.framework import Entry
from ocelescope_module_streaming.stream import ObjectRef

T = TypeVar("T")


def normalize(values: Sequence[float]) -> list[float]:
    """Min-max normalizes `values` into [0, 1]; all zero if they are equal."""
    if not values:
        return []
    low, high = min(values), max(values)
    if high <= low:
        return [0.0] * len(values)
    return [(value - low) / (high - low) for value in values]


def normalize_map(values: Mapping[T, float]) -> dict[T, float]:
    """Min-max normalizes the values of a mapping."""
    return dict(zip(values, normalize(list(values.values())), strict=True))


def owner_type(key: Any, entry: Entry[Any]) -> str | None:
    """The object type an entry belongs to: the key's if it is an object, else the value's.

    Values may name their object (`obj`) or their type (`object_type`).
    """
    if isinstance(key, ObjectRef):
        return key.type
    value = entry.value
    obj = getattr(value, "obj", None)
    if isinstance(obj, ObjectRef):
        return obj.type
    object_type = getattr(value, "object_type", None)
    return object_type if isinstance(object_type, str) else None
