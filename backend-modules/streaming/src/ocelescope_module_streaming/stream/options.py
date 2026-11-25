"""Which kinds of items a replay includes."""

from pydantic import BaseModel, ConfigDict, Field


class StreamOptions(BaseModel):
    """The item kinds of a replayed stream.

    Leaving out kinds an algorithm ignores changes nothing in its buffers, but it changes the
    positions of the remaining items, and positions are what heuristics measure time in.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    events: bool = Field(default=True, title="Events")
    o2o_updates: bool = Field(default=True, title="O2O updates")
    attribute_updates: bool = Field(default=False, title="Attribute updates")
