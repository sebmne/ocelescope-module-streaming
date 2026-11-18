"""The base class of heuristics (Definition def:configuration)."""

from abc import ABC
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel

from ocelescope_module_streaming.framework.buffer import Buffer, Stats

if TYPE_CHECKING:
    from ocelescope_module_streaming.framework.algorithm import BufferAlgorithm

P = TypeVar("P", bound=BaseModel)


class NoParameters(BaseModel):
    """The parameters of a heuristic without parameters."""


class Heuristic(ABC, Generic[P]):
    """Scores the keys of a buffer; a higher score means a key is evicted sooner.

    A heuristic sees what the run history determines: the position of the current item, each
    key's bookkeeping, and the algorithm's state. Each buffer gets its own instance, so a
    heuristic may keep state of its own, e.g. a random generator.

    Attributes:
        label: The name shown to users.
        parameters_model: The parameters `P`, whose JSON schema clients use to configure it.
    """

    label: ClassVar[str]
    parameters_model: ClassVar[type[BaseModel]] = NoParameters

    def __init__(self, parameters: P) -> None:
        self.parameters = parameters

    def scores(
        self, buffer: Buffer[Any, Any], position: int, algorithm: "BufferAlgorithm[Any, Any]"
    ) -> dict[Any, float]:
        """The score of every key of `buffer` while the item at `position` is processed.

        Override for scores that depend on all keys, e.g. min-max normalized ones.
        """
        return {key: self.score(key, buffer.stats(key), position, algorithm) for key in buffer.keys()}

    def score(self, key: Any, stats: Stats, position: int, algorithm: "BufferAlgorithm[Any, Any]") -> float:
        """The score of `key` with bookkeeping `stats`; override this or `scores`."""
        raise NotImplementedError


def normalized(scores: dict[Any, float]) -> dict[Any, float]:
    """Min-max normalizes `scores`; all 0 if they are equal."""
    if not scores:
        return {}
    low, high = min(scores.values()), max(scores.values())
    return {key: (score - low) / (high - low) if high > low else 0.0 for key, score in scores.items()}
