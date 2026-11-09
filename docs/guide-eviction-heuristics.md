# Guide: implementing an eviction heuristic

An eviction heuristic decides which buffer entries an algorithm forgets. It
knows nothing about the algorithm it runs in, so a new heuristic immediately
works for every algorithm and every buffer, in the run form, the API and
scripts.

This guide builds three heuristics step by step. All code in this guide is
executed by `tests/test_docs.py`, so it stays correct.

Read [Architecture](architecture.md#eviction-modes) for eviction modes and the
run loop first. The formal definition is `def:heuristic` in
[`definitions.tex`](definitions.tex).

## The interface

A heuristic is a subclass of `framework.Heuristic`. Everything is optional;
implement what your heuristic needs.

| Member | Used for | Called |
|---|---|---|
| `modes` | Which eviction modes the heuristic supports: `CAPACITY`, `EXPIRY` or both (then `BOTH` is allowed too). Default: capacity only. | when the run is prepared |
| `score(key, entry, ctx) -> float` | Capacity mode: rank one key; **higher is evicted first**. | while a buffer is over capacity |
| `scores(candidates, ctx) -> list[float]` | Capacity mode: rank all candidates at once, e.g. to normalize. Default: `score` per key. | instead of `score` |
| `order` | Capacity mode: an `EvictionOrder` the buffer maintains, so it evicts in constant time without scoring (FIFO, LIFO, LRU). | instead of `scores` |
| `deadline(key, entry, ctx) -> int \| None` | Expiry mode: the position at which the key should go; `None` means never. | on every write, and again when the deadline is reached |
| `on_item(item, ctx)` | Update the heuristic's state from every stream item, before the algorithm sees it. | once per item |
| `on_write(key, entry, ctx)` | Update state after a key was written. Called once per item and key, after the algorithm's update. | after `update` |
| `on_evict(key, entry, ctx, reason)` | Update state after a key left the buffer (`capacity`, `expired` or `discarded`). | after the algorithm's `finish` |

What a heuristic sees:

- `entry`: the buffered `value` and its bookkeeping — `first` and `last`
  (positions of the first and last write) and `freq` (number of writes).
- `ctx`: a `Context` with `position` and `timestamp` of the current item and
  the `algorithm`, i.e. the whole algorithm state. Read from it, never write.

Rules:

- Keys touched by the current item are never offered for eviction; you do not
  need to handle them.
- **State a heuristic keeps counts toward memory.** Keep it bounded by the
  number of object types or activities, or by the buffer's own size (and
  delete per-key state in `on_evict`). Never keep state per object that
  outlives the object's entry.
- One heuristic instance serves one buffer. The run creates a fresh instance
  per buffer from the registered parameters.
- Make randomness seedable (see `RandomReplacement`), so runs are repeatable.

## Example 1: a capacity heuristic

Evict keys that were written only once first (they are likely noise), and
among those the least recently written one:

```python
from typing import Any

from ocelescope_module_streaming.catalog import register_heuristic
from ocelescope_module_streaming.framework import Context, Entry, Heuristic

ONE_SHOT_BONUS = 1e12


@register_heuristic(
    key="example_one_shot_first",
    label="One-shot first",
    description="Evicts keys written only once first, then the least recently written key.",
)
class OneShotFirst(Heuristic):
    """Prefers keys written only once; LRU among equals."""

    def score(self, key: Any, entry: Entry[Any], ctx: Context) -> float:
        age = ctx.position - entry.last
        return age + (ONE_SHOT_BONUS if entry.freq == 1 else 0)
```

`register_heuristic` adds it to the catalog: the frontend offers it in every
buffer's *Heuristic* select (in capacity modes) and `RunConfig` accepts
`heuristic="example_one_shot_first"`. Without parameters, no `params` model is
needed.

Try it on a small stream:

```python
from datetime import UTC, datetime, timedelta

from ocelescope_module_streaming.algorithms import StreamingOCDFG
from ocelescope_module_streaming.catalog import NoParams
from ocelescope_module_streaming.evaluation import BufferMonitor
from ocelescope_module_streaming.framework import BufferConfig, run
from ocelescope_module_streaming.stream import Event, ObjectRef, Relation, StreamItem


def stream(*events: tuple[str, list[tuple[str, str]]]) -> list[StreamItem]:
    """Events as (activity, [(object type, object id), ...]), one day apart."""
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        StreamItem(Event(activity, tuple(Relation(ObjectRef(i, t)) for t, i in objects)), start + timedelta(days=n))
        for n, (activity, objects) in enumerate(events)
    ]


example = stream(
    ("create", [("order", "o1")]),
    ("create", [("order", "o2")]),
    ("pay", [("order", "o1")]),
    ("create", [("order", "o3")]),
)
algorithm = StreamingOCDFG(NoParams(), {"objects": BufferConfig(capacity=2, heuristic=OneShotFirst())})
monitor = BufferMonitor()
run(algorithm, example, [monitor])

# o2 was written once; o1 twice. When o3 arrives, o2 is evicted.
assert {obj.id for obj in algorithm.tracker.objects} == {"o1", "o3"}
assert monitor.statistics()["objects"].evictions == 1
```

## Example 2: an expiry heuristic with state and parameters

Expire an object after `factor` times the typical gap between writes of its
object type. The heuristic learns the typical gap per type while the stream
runs:

```python
import math
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.framework import EvictionMode, EvictionReason
from ocelescope_module_streaming.heuristics.ranking import owner_type


class AdaptiveTimeoutParams(BaseModel):
    """Parameters of `AdaptiveTimeout`. Field descriptions become form help texts."""

    model_config = ConfigDict(extra="forbid")

    factor: float = Field(default=3.0, gt=0, description="Multiple of the typical gap after which a key expires.")
    initial: int = Field(default=100, ge=1, description="Gap assumed for a type before one was observed.")
    smoothing: float = Field(default=0.1, gt=0, le=1, description="Weight of a new gap in the running mean.")


@register_heuristic(
    key="example_adaptive_timeout",
    label="Adaptive timeout",
    description="Evicts a key after a multiple of the typical gap between writes of its object type.",
    params=AdaptiveTimeoutParams,
)
class AdaptiveTimeout(Heuristic):
    """Expires keys after `factor` times the running mean gap of their object type."""

    modes: ClassVar[frozenset[EvictionMode]] = frozenset({EvictionMode.EXPIRY})

    def __init__(self, factor: float = 3.0, initial: int = 100, smoothing: float = 0.1) -> None:
        self.factor = factor
        self.initial = initial
        self.smoothing = smoothing
        self.gaps: dict[str, float] = {}  # per object type: bounded by the number of types
        self.expired = 0

    def on_write(self, key: Any, entry: Entry[Any], ctx: Context) -> None:
        object_type = owner_type(key, entry) or "*"
        if entry.freq > 1:  # mean gap of this key so far
            gap = (entry.last - entry.first) / (entry.freq - 1)
            previous = self.gaps.get(object_type, gap)
            self.gaps[object_type] = (1 - self.smoothing) * previous + self.smoothing * gap

    def deadline(self, key: Any, entry: Entry[Any], ctx: Context) -> int | None:
        object_type = owner_type(key, entry) or "*"
        return entry.last + math.ceil(self.factor * self.gaps.get(object_type, self.initial))

    def on_evict(self, key: Any, entry: Entry[Any], ctx: Context, reason: EvictionReason) -> None:
        if reason is EvictionReason.EXPIRED:
            self.expired += 1
```

Notes:

- `modes` says the heuristic only supports expiry. Configuring it with a
  capacity is rejected with a clear error; the frontend only offers it under
  *Heuristic schedule*.
- The parameter model is validated before the heuristic is created
  (`AdaptiveTimeout(**params.model_dump())`), and its JSON schema renders the
  form. Use `extra="forbid"` so typos are errors.
- `deadline` is called again when the scheduled position is reached. If the
  learned gap grew meanwhile, the key is rescheduled; if it shrank, the key
  still waits for its old deadline (scheduled expiry, `def:run`).
- `owner_type` finds the object type of an entry: the key if it is an
  `ObjectRef`, otherwise the value's `obj` or `object_type` attribute.

Run it from a configuration, as the API does:

```python
from ocelescope_module_streaming.runs import BufferSetting, RunConfig, prepare_run

config = RunConfig(
    ocel_id="unused",
    algorithm="ocdfg",
    buffers={"objects": BufferSetting(heuristic="example_adaptive_timeout", heuristic_params={"factor": 2})},
)
prepared = prepare_run(config)  # mode "expiry" is derived: no capacity, heuristic set
objects = prepared.algorithm.buffers[0]
assert objects.mode is EvictionMode.EXPIRY and isinstance(objects.heuristic, AdaptiveTimeout)

run(prepared.algorithm, example + stream(*[("tick", [("clock", f"c{i}")]) for i in range(300)]))
assert objects.heuristic.expired > 0
```

## Example 3: ranking all candidates at once

Some rankings need the whole candidate set, e.g. min–max normalized features
that are added up (as in Liss et al.). Override `scores` instead of `score`:

```python
from collections.abc import Sequence

from ocelescope_module_streaming.heuristics.ranking import normalize


class StaleAndRare(Heuristic):
    """Sum of normalized age and normalized rarity; the highest sum is evicted."""

    def scores(self, candidates: Sequence[tuple[Any, Entry[Any]]], ctx: Context) -> list[float]:
        ages = normalize([ctx.position - entry.last for _, entry in candidates])
        rarities = normalize([-entry.freq for _, entry in candidates])
        return [age + rarity for age, rarity in zip(ages, rarities, strict=True)]

    def score(self, key: Any, entry: Entry[Any], ctx: Context) -> float:
        return self.scores([(key, entry)], ctx)[0]


run(StreamingOCDFG(NoParams(), {"objects": BufferConfig(capacity=2, heuristic=StaleAndRare())}), example)
```

Heuristics can also be used without registering them, as here: pass an
instance to `BufferConfig` directly. Only registered heuristics are available
in the frontend and the API.

## Constant-time eviction orders

Scoring scans every buffered key on each eviction, which gets slow for large
buffers. If a heuristic's ranking is a fixed order of the keys, declare it as
`order` and the buffer maintains that order instead:

| `EvictionOrder` | Order | Used by |
|---|---|---|
| `OLDEST_FIRST` | insertion order; rewrites keep their place | `FIFO` |
| `NEWEST_FIRST` | reverse insertion order | `LIFO` |
| `LEAST_RECENT_FIRST` | write order; each write moves the key to the end | `LRU` |

```python
from ocelescope_module_streaming.framework import EvictionOrder


class OldestFirst(Heuristic):
    order: ClassVar[EvictionOrder | None] = EvictionOrder.OLDEST_FIRST

    def score(self, key: Any, entry: Entry[Any], ctx: Context) -> float:
        return ctx.position - entry.first  # must rank like the order
```

Keep `score` consistent with the order: it defines the heuristic in
`definitions.tex` and is used when the heuristic is combined with others
(e.g. inside `priority`). `tests/test_fast_eviction.py` shows how to check
that the order and the score agree.

## Making it permanent

1. Put the class in a module under `heuristics/` (e.g.
   `heuristics/adaptive.py`) and **import it in `heuristics/__init__.py`**.
   The catalog loads that package on first use; a heuristic in a module that
   is never imported does not appear.
2. Use a unique `key`. It is stored in run configurations, so do not rename it
   later.
3. Add the definition to `docs/definitions.tex` (section *Eviction
   Heuristics*): state, score or deadline, and state updates.
4. Add tests (see `tests/test_eviction.py`, `tests/test_lifecycle.py` and
   `tests/test_liss_heuristics.py` for patterns):
   - victims or deadlines on a handful of hand-written keys,
   - state updates for every eviction reason,
   - a run through `prepare_run` with its parameters,
   - for expiry heuristics: rescheduling and a shrinking deadline.
5. Run `pnpm run check:backend` and `pnpm run build:modules` (the catalog
   schema reaches the frontend through the generated client).

To compare it with the built-ins, run the same algorithm, buffer capacity and
log with each heuristic and compare the scores and the buffer statistics
(`evictions_by_reason`, `premature_evictions`).
