from datetime import datetime

from ocelescope.resource.default.dfg import DFGActivity, DFGEdge, DFGObject

from ocelescope_module_streaming.algorithms import NoConfig, StreamingAlgorithm
from ocelescope_module_streaming.models import StreamingDFG
from ocelescope_module_streaming.observers import GraphUnion
from ocelescope_module_streaming.stream import Event, ObjectRef, Relation, Stream, StreamItem

ORDER = ObjectRef("o1", "Order")


class LastStep(StreamingAlgorithm[NoConfig, StreamingDFG]):
    """Keeps only the newest directly-follows step, like a buffer of capacity one."""

    label = "Last step"

    def __init__(self, config: NoConfig) -> None:
        super().__init__(config)
        self.step: tuple[str | None, str] | None = None

    def consume(self, stream: Stream) -> StreamingDFG:
        for x, _ in stream:
            assert isinstance(x, Event)
            self.step = (self.step[1] if self.step else None, x.activity)
        return self.model()

    def model(self) -> StreamingDFG:
        if self.step is None:
            return StreamingDFG()
        source, target = self.step
        return StreamingDFG(
            activities=[DFGActivity(name=a) for a in {source, target} if a],
            object_types=[DFGObject(name="Order")],
            edges=[DFGEdge(object_type="Order", source=source, target=target, count=1)],
        )


def test_the_union_keeps_elements_that_are_gone_by_the_end() -> None:
    algorithm, union = LastStep(NoConfig()), GraphUnion()
    algorithm.attach(union)
    algorithm.run(iter(StreamItem(Event(a, (Relation(ORDER),)), datetime(2026, 1, 1)) for a in ("a", "b", "c")))

    graph = union.graph()
    assert graph is not None
    assert {e.id for e in graph.edges} == {"Order:None->a", "Order:a->b", "Order:b->c"}
    assert {n.id for n in graph.nodes} == {"start_Order", "a", "b", "c"}
    assert [e.id for e in algorithm.model().visualize().edges] == ["Order:b->c"]  # the final model alone
