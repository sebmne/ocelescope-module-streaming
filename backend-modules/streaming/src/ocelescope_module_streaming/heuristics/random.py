import random
from typing import Any

from pydantic import BaseModel, Field

from ocelescope_module_streaming.framework import BufferAlgorithm, Heuristic, Stats


class RandomParameters(BaseModel):
    seed: int = Field(default=0, title="Seed", description="Makes runs repeatable.")


class RandomReplacement(Heuristic[RandomParameters]):
    """Random replacement: independent and uniform in [0, 1]."""

    label = "Random replacement"
    parameters_model = RandomParameters

    def __init__(self, parameters: RandomParameters) -> None:
        super().__init__(parameters)
        self._random = random.Random(parameters.seed)

    def score(self, key: Any, stats: Stats, position: int, algorithm: BufferAlgorithm[Any, Any]) -> float:
        return self._random.random()
