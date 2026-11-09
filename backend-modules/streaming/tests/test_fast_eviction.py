"""Constant-time eviction orders (FIFO, LIFO, LRU) agree with their scores."""

import random
from itertools import islice
from typing import Any, ClassVar

import pytest
from ocelescope import OCEL
from support import step

from ocelescope_module_streaming.algorithms import LissTotem, StreamingOCDFG, TotemParams
from ocelescope_module_streaming.catalog import NoParams, algorithms
from ocelescope_module_streaming.framework import Buffer, BufferConfig, EvictionOrder, Heuristic, run
from ocelescope_module_streaming.heuristics import FIFO, LIFO, LRU
from ocelescope_module_streaming.ocel import ocel_stream


class ScannedFIFO(FIFO):
    """FIFO without its eviction order, so every eviction scores all keys."""

    order: ClassVar[EvictionOrder | None] = None


@pytest.mark.parametrize("heuristic", [FIFO, LIFO, LRU])
@pytest.mark.parametrize("seed", range(20))
def test_victim_has_a_highest_score(heuristic: type[Heuristic], seed: int) -> None:
    rng = random.Random(seed)
    buffer: Buffer[int, int] = Buffer("b", BufferConfig(capacity=5, heuristic=heuristic()))
    for position in range(1, 60):
        step(buffer, position)
        for _ in range(rng.randint(0, 3)):
            buffer.put(rng.randint(0, 12), position)
        buffer.flush_writes()
        while buffer.over_capacity() and (victim := buffer.victim()) is not None:
            ctx = buffer._ctx  # noqa: SLF001
            assert ctx is not None and buffer.heuristic is not None
            candidates = [(k, e) for k in buffer if k not in buffer.touched and (e := buffer.entry(k)) is not None]
            scores = dict(zip((k for k, _ in candidates), buffer.heuristic.scores(candidates, ctx), strict=True))
            assert scores[victim] == max(scores.values())
            buffer.evict(victim)


def test_lru_moves_rewritten_keys_to_the_end() -> None:
    buffer: Buffer[str, int] = Buffer("b", BufferConfig(capacity=2, heuristic=LRU()))
    for position, key in enumerate("aba", start=1):
        step(buffer, position)
        buffer.put(key, position)
    step(buffer, 4)
    buffer.put("c", 4)
    assert buffer.victim() == "b"
    buffer.evict("b")
    step(buffer, 5)
    assert buffer.victim() == "a"


def test_fast_fifo_equals_scanned_fifo_on_ocdfg(container_logistics: OCEL) -> None:
    def model(heuristic: Heuristic) -> Any:
        spec = algorithms.get("ocdfg")
        algorithm = StreamingOCDFG(NoParams(), {"objects": BufferConfig(capacity=50, heuristic=heuristic)})
        with ocel_stream(container_logistics, spec.stream) as stream:
            return run(algorithm, stream)

    assert model(FIFO()) == model(ScannedFIFO())


def test_fast_fifo_equals_scanned_fifo_on_totem(container_logistics: OCEL) -> None:
    def model(heuristic: type[Heuristic]) -> Any:
        spec = algorithms.get("liss_totem")
        config = {name: BufferConfig(capacity=100, heuristic=heuristic()) for name in ("lifespans", "log_cardinality")}
        algorithm = LissTotem(TotemParams(), config)
        with ocel_stream(container_logistics, spec.stream) as stream:
            return run(algorithm, islice(stream, 3000))

    assert model(FIFO) == model(ScannedFIFO)
