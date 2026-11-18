import pytest

from ocelescope_module_streaming.framework import Buffer, Stats


def test_uses_count_once_per_item_and_only_while_updating() -> None:
    buffer: Buffer[str, int] = Buffer("b", "B")
    buffer.begin(1)
    assert buffer.get("k") is None  # reading a missing key uses it
    buffer.put("k", 1)
    buffer.put("k", 2)
    buffer.end()
    assert buffer.used == {"k"} and buffer.stats("k") == Stats(ins=1, last=1, freq=1)

    buffer.begin(3)
    assert "k" in buffer
    buffer.end()
    buffer.put("k", 3)  # e.g. by fin: no use
    assert buffer.stats("k") == Stats(ins=1, last=3, freq=2)


def test_keys_inserted_outside_an_update_have_no_uses() -> None:
    buffer: Buffer[str, int] = Buffer("b", "B", sink=True)
    buffer.begin(4)
    buffer.end()
    buffer.put("end", 1)
    assert buffer.stats("end") == Stats(ins=4, last=4, freq=0) and not buffer.used


def test_a_key_created_again_starts_a_new_stay() -> None:
    buffer: Buffer[str, int] = Buffer("b", "B")
    buffer.begin(1)
    buffer.put("k", 1)
    buffer.end()
    buffer.delete("k")
    buffer.begin(5)
    buffer.put("k", 1)
    buffer.end()
    assert buffer.stats("k") == Stats(ins=5, last=5, freq=1)
    with pytest.raises(KeyError):
        buffer.delete("missing")
