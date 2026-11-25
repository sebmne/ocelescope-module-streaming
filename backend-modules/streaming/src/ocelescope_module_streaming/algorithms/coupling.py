"""The parameter for the optional coupled removal (buffer synchronization) of Liss et al."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CouplingMode = Literal["off", "objects", "object_types"]


class CouplingParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coupled_removal: CouplingMode = Field(
        default="off",
        title="Coupled removal",
        description=(
            "After an eviction, delete the entries of objects (or object types) that no longer occur in the "
            "buffer they were evicted from from the other buffers, as in Liss et al.'s buffer synchronization."
        ),
    )
