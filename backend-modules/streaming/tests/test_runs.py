import pytest

from ocelescope_module_streaming.heuristics import RandomReplacement
from ocelescope_module_streaming.runs import BufferSetting, InvalidRunConfig, RunConfig, prepare_run


def config(**buffers: BufferSetting) -> RunConfig:
    return RunConfig(ocel_id="log", algorithm="ocdfg", buffers=buffers)


def test_prepare_run_builds_configured_buffers() -> None:
    prepared = prepare_run(config(objects=BufferSetting(capacity=10, heuristic="random", heuristic_params={"seed": 4})))
    objects = prepared.algorithm.buffers[0]
    assert objects.capacity == 10 and isinstance(objects.heuristic, RandomReplacement)
    assert prepared.name == "OC-DFG (counts) (objects Random 10)"


@pytest.mark.parametrize(
    ("run_config", "message"),
    [
        (RunConfig(ocel_id="log", algorithm="nope"), "Unknown algorithm"),
        (config(nope=BufferSetting()), "has no buffer nope"),
        (config(objects=BufferSetting(capacity=3)), "no heuristic"),
        (config(objects=BufferSetting(capacity=3, heuristic="nope")), "Unknown heuristic"),
        (config(objects=BufferSetting(capacity=3, heuristic="random", heuristic_params={"x": 1})), "Invalid"),
    ],
)
def test_prepare_run_rejects_invalid_configs(run_config: RunConfig, message: str) -> None:
    with pytest.raises(InvalidRunConfig, match=message):
        prepare_run(run_config)
