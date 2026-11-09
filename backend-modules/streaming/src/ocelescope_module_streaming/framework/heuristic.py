"""Eviction heuristics (definitions.tex: def:heuristic)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from ocelescope_module_streaming.framework.algorithm import StreamingAlgorithm
    from ocelescope_module_streaming.framework.buffer import Entry


class EvictionMode(StrEnum):
    """How a buffer decides what to evict.

    Attributes:
        CAPACITY: Keep at most `capacity` entries; evict the highest `Heuristic.score` first.
        EXPIRY: No size limit; evict entries whose `Heuristic.deadline` has passed.
        BOTH: Expiry first, then capacity.
    """

    CAPACITY = "capacity"
    EXPIRY = "expiry"
    BOTH = "both"


class EvictionReason(StrEnum):
    """Why a key left a buffer.

    Attributes:
        CAPACITY: Evicted because the buffer exceeded its capacity.
        EXPIRED: Evicted because its deadline passed.
        DISCARDED: Removed by the algorithm itself, without eviction handling.
    """

    CAPACITY = "capacity"
    EXPIRED = "expired"
    DISCARDED = "discarded"


@dataclass(frozen=True, slots=True)
class Context:
    """What a heuristic may read while processing the item at `position`.

    Attributes:
        algorithm: The algorithm owning the buffer, i.e. the state σ.
        position: The 1-based position of the current item.
        timestamp: The timestamp of the current item.
    """

    algorithm: "StreamingAlgorithm[Any]"
    position: int
    timestamp: datetime


class Heuristic:
    """Base class for eviction heuristics.

    A heuristic supports capacity mode by implementing `score` and expiry mode by implementing
    `deadline`, and declares the supported modes in `modes`. It may keep its own state (θ),
    updated through `on_write` and `on_evict`; that state must not grow with the number of
    objects.

    Heuristics may read any state of the algorithm through the context.
    """

    modes: ClassVar[frozenset[EvictionMode]] = frozenset({EvictionMode.CAPACITY})
    """The supported modes among CAPACITY and EXPIRY; BOTH is supported if both are."""

    @classmethod
    def supported_modes(cls) -> tuple[EvictionMode, ...]:
        """The modes a buffer using this heuristic may be configured with."""
        modes = [mode for mode in (EvictionMode.CAPACITY, EvictionMode.EXPIRY) if mode in cls.modes]
        if len(modes) == 2:
            modes.append(EvictionMode.BOTH)
        return tuple(modes)

    def score(self, key: Any, entry: "Entry[Any]", ctx: Context) -> float:
        """Scores a buffered key in capacity mode; higher scores are evicted first.

        Args:
            key: The buffered key.
            entry: The entry stored under `key`.
            ctx: The current context.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support capacity mode")

    def deadline(self, key: Any, entry: "Entry[Any]", ctx: Context) -> int | None:
        """Returns the position at which `key` should be evicted in expiry mode.

        Called when `key` is written and again when its scheduled deadline is reached. If the
        new deadline lies after the current position, the key is rescheduled; otherwise it is
        evicted.

        Args:
            key: The buffered key.
            entry: The entry stored under `key`.
            ctx: The current context.

        Returns:
            The deadline position, or None if the key should never expire.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support expiry mode")

    def on_write(self, key: Any, entry: "Entry[Any]", ctx: Context) -> None:  # noqa: B027
        """Updates the heuristic state after `key` was written. Does nothing by default.

        Called once per item for every written key, after the algorithm's update.
        """

    def on_evict(self, key: Any, entry: "Entry[Any]", ctx: Context, reason: EvictionReason) -> None:  # noqa: B027
        """Updates the heuristic state after `key` left the buffer. Does nothing by default.

        Called after the algorithm's `finish`, or right after removal for discarded keys.
        """

    def __repr__(self) -> str:
        return type(self).__name__
