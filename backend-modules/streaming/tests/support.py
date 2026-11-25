"""Shared test data: the running example of the paper and the bundled container-logistics log."""

from pathlib import Path

from ocelescope_module_streaming.stream import StreamItem, event

ORDER, ITEM = "order", "item"

LOG_PATH = Path(__file__).resolve().parents[3] / "data" / "event_logs" / "container_logistics.db"


def running_example() -> list[StreamItem]:
    """S_ex of the paper (Example "Running Example"), with timestamp i for item i."""
    spec = [
        ("place", ["o1", "i1"]),
        ("place", ["o2", "i2"]),
        ("pick", ["i1"]),
        ("pay", ["o1"]),
        ("ship", ["o1", "i1"]),
        ("pick", ["i2"]),
        ("place", ["o3", "i3"]),
        ("pay", ["o2"]),
        ("ship", ["o2", "i2"]),
    ]
    return [
        event(activity, [(o, ORDER if o.startswith("o") else ITEM) for o in objects], position)
        for position, (activity, objects) in enumerate(spec, start=1)
    ]
