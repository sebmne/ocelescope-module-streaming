"""Sampling of buffer sizes during a run."""

from support import event, stream_of

from ocelescope_module_streaming.algorithms import StreamingOCDFG
from ocelescope_module_streaming.catalog import NoParams
from ocelescope_module_streaming.evaluation import BufferSampler
from ocelescope_module_streaming.framework import BufferConfig, run
from ocelescope_module_streaming.heuristics import FIFO
from ocelescope_module_streaming.runs import RunConfig


def run_sampled(items: int, expected: int, samples: int = 200) -> BufferSampler:
    algorithm = StreamingOCDFG(NoParams(), {"objects": BufferConfig(capacity=3, heuristic=FIFO())})
    sampler = BufferSampler(expected, samples)
    run(algorithm, stream_of(*(event("a", t=str(i)) for i in range(items))), [sampler])
    sampler.finish(items, algorithm)
    return sampler


def test_short_streams_are_sampled_at_every_item() -> None:
    series = run_sampled(items=5, expected=5).series()
    assert series.positions == [1, 2, 3, 4, 5]
    assert series.sizes["objects"] == [1, 2, 3, 3, 3]
    assert series.capacities == {"objects": 3, "arcs": None, "starts": None, "ends": None}


def test_long_streams_get_at_most_the_requested_samples() -> None:
    series = run_sampled(items=1000, expected=1000, samples=200).series()
    assert len(series.positions) == 200
    assert series.positions[0] == 5 and series.positions[-1] == 1000
    assert all(len(sizes) == 200 for sizes in series.sizes.values())


def test_longer_stream_than_expected_ends_with_the_last_item() -> None:
    series = run_sampled(items=120, expected=100, samples=10).series()
    assert len(series.positions) == 10 and series.positions[-1] == 120
    assert series.positions == sorted(series.positions)


def test_monitoring_is_off_by_default() -> None:
    assert RunConfig(ocel_id="log", algorithm="ocdfg").monitor_buffers is False
