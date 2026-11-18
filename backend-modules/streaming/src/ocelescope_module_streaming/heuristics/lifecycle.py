import math
from collections import Counter
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from ocelescope_module_streaming.framework import Buffer, BufferAlgorithm, Heuristic


class LifecycleParameters(BaseModel):
    t_int: int = Field(default=200, ge=0, title="T_int", description="Items an object is surely active.")
    t_max: int = Field(default=1000, ge=1, title="T_max", description="Items an object may be inactive at most.")
    z: float = Field(default=1.0, gt=0, title="z", description="Width of the credible interval.")

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.t_int >= self.t_max:
            raise ValueError("T_int must be smaller than T_max")
        return self


class Lifecycle(Heuristic[LifecycleParameters]):
    """Mühlmeyer et al.'s lifecycle estimation for the object buffer of the directly-follows
    algorithm: how far an object's inactivity exceeds its expected lifetime, learned from the
    end activities of evicted objects (Definition def:lifecycle)."""

    label = "Lifecycle"
    parameters_model = LifecycleParameters

    def scores(self, buffer: Buffer[Any, Any], position: int, algorithm: BufferAlgorithm[Any, Any]) -> dict[Any, float]:
        ends: Buffer[tuple[str, str], int] = algorithm.buffers["ends"]
        completed = Counter[str]()
        for (object_type, _), count in ends.items():
            completed[object_type] += count
        return {
            obj: (position - buffer.stats(obj).last)
            / self.life(completed[object_type], ends.get((object_type, activity)) or 0)
            for obj, (object_type, activity) in buffer.items()
        }

    def life(self, n: int, n_a: int) -> int:
        """The expected lifetime of an object whose last activity ended `n_a` of `n` lifecycles."""
        p = (n_a + 1) / (n + 2)
        v = (n_a + 1) * (n - n_a + 1) / ((n + 2) ** 2 * (n + 3))
        conf = max(0.0, p - self.parameters.z * math.sqrt(v))
        t_int, t_max = self.parameters.t_int, self.parameters.t_max
        if conf == 0:
            return t_max
        if conf >= 0.9999:
            return t_int + 1
        return t_int + math.ceil((t_max - t_int) * 0.95 ** (conf / (1 - conf)))
