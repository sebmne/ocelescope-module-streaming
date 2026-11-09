import pytest

from ocelescope_module_streaming.framework import Buffer, BufferConfig
from ocelescope_module_streaming.heuristics import FIFO


def test_bookkeeping_tracks_first_last_and_frequency() -> None:
    buffer: Buffer[str, int] = Buffer("b")
    buffer.start_step(1)
    buffer.put("k", 1)
    buffer.start_step(4)
    buffer.put("k", 2)
    entry = buffer.entry("k")
    assert entry is not None
    assert (entry.value, entry.first, entry.last, entry.freq) == (2, 1, 4, 2)


def test_touched_keys_are_reset_per_step() -> None:
    buffer: Buffer[str, int] = Buffer("b")
    buffer.start_step(1)
    buffer.put("k", 1)
    assert set(buffer.touched) == {"k"}
    buffer.start_step(2)
    assert set(buffer.touched) == set()
    assert buffer.get("k") == 1  # reading does not touch
    assert set(buffer.touched) == set()


def test_discard_removes_without_eviction() -> None:
    buffer: Buffer[str, int] = Buffer("b")
    buffer.put("k", 1)
    assert buffer.discard("k") == 1
    assert "k" not in buffer and buffer.discard("k") is None


def test_buffer_config_validation() -> None:
    with pytest.raises(ValueError):
        BufferConfig(capacity=-1, heuristic=FIFO())
    with pytest.raises(ValueError):
        BufferConfig(capacity=3)
    assert Buffer("b", BufferConfig()).capacity is None
