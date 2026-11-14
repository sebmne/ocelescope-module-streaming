from typing import Any

from ocelescope_backend.app.internal.session import Session

from ocelescope_module_streaming.algorithms import ItemProcessed, Observer, RunEvent, StreamingAlgorithm


class Snapshot(Observer):
    """Stores the current model every `every` items as a hidden session resource, for live views.

    Each snapshot gets a new id, so clients notice the change. The previous snapshot is kept
    until the next one exists, so a client still loading it does not fail.
    """

    def __init__(self, session: Session, name: str, every: int = 1_000) -> None:
        self.session = session
        self.name = name
        self.every = every
        self.ids: list[str] = []

    @property
    def latest(self) -> str | None:
        """The id of the newest snapshot, if any."""
        return self.ids[-1] if self.ids else None

    def notify(self, algorithm: StreamingAlgorithm[Any, Any], event: RunEvent) -> None:
        if isinstance(event, ItemProcessed) and event.position % self.every == 0:
            self.ids.append(self.session.add_resource(algorithm.model(), self.name, hidden=True))
            while len(self.ids) > 2:
                self.session.delete_resource(self.ids.pop(0))

    def clear(self) -> None:
        """Deletes all snapshots."""
        while self.ids:
            self.session.delete_resource(self.ids.pop())
