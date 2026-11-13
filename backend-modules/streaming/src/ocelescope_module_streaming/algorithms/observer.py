"""Observers of streaming algorithms (observer pattern: the algorithm is the subject)."""

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ocelescope_module_streaming.algorithms.algorithm import StreamingAlgorithm
    from ocelescope_module_streaming.algorithms.events import RunEvent


class Observer(Protocol):
    """Is notified of the events of the algorithms it is attached to.

    Override `notify` and react to the event types you need; read further state, e.g. the
    current model, from the algorithm.
    """

    def notify(self, algorithm: "StreamingAlgorithm[Any]", event: "RunEvent") -> None:
        """Called for every event of `algorithm`."""
