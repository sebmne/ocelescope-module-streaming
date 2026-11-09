# Guide: implementing a streaming algorithm

A streaming algorithm turns a stream into a process model. In this framework
it is a composition of **blocks** — reusable parts that own buffers — plus a
function that builds the model from the blocks' snapshots. Because all state
lives in buffers, every eviction heuristic and mode works for the new
algorithm without extra code.

This guide builds an algorithm from existing blocks, then writes a new block.
All code in this guide is executed by `tests/test_docs.py`.

Read [Architecture](architecture.md) first. The formal definitions are
`def:algorithm`, `def:run` and section *Building Blocks* in
[`definitions.tex`](definitions.tex).

## The interface

Subclass `framework.StreamingAlgorithm[M]`, where `M` is the model type:

| Member | Purpose |
|---|---|
| `__init__(params, config)` | Create the buffers with `self.create_buffers(*names)` (it applies the per-buffer `config` and rejects unknown names) and wire the blocks. |
| `buffers` | All buffers, in the order the run loop evicts from them. |
| `update(item, position)` | Process one stream item: dispatch it to the blocks. |
| `finish(buffer, key, value)` | Called after `key` was evicted from `buffer`. Forward it to the blocks, which may record what the key contributed (e.g. an end activity). |
| `after_evictions(position)` | Optional, once per item after all evictions, e.g. to synchronize buffers with `Buffer.discard`. |
| `model()` | Build the current model from the blocks' snapshots. Called at the end of a run, but may be called at any time. |

## Available blocks

All in `blocks/`, all independent of Ocelescope:

| Block | Input | Buffers it uses | Offers |
|---|---|---|---|
| `ObjectTracker(objects)` | `update(event, time)` | `objects`: object → `LastSeen(activity, time)` | emits `Transition(obj, previous, previous_time, activity, time, objects, relations)` per object of an event and `Retired(obj, activity)` when an object is evicted; `last_activity(obj)`, `live()` |
| `DirectlyFollowsCounters(tracker, arcs, starts, ends)` | tracker events | counters per `(a, b, type)`, `(a, type)` | `snapshot() -> DFSnapshot(arcs, starts, ends)`; end activities from evicted *and* live objects |
| `DirectlyFollowsLog(tracker, arcs)` | tracker events | observation log of `ArcObservation` | the arc observations (Liss et al.) |
| `ActivityTypeRelations(activities, relations)` | `update(event)` | counters N(a), N(a,t), N>1(a,t) | `snapshot() -> RelationsSnapshot(rel, con, deficient)` |
| `DivergenceIndex(index, divergent)` | `update(event)` | `(a, t, h(O⇂t)) → h(O)`, divergent pairs | `snapshot()`: divergent `(activity, type)` pairs |
| `ObjectInteractions(lifespans, log_cardinality, event_cardinality)` | `update(event or O2O, time)` | lifespans and two observation logs | TOTeM inputs (Liss et al.) |
| `coupled_removal(pairs)` | – | – | keeps only entries whose object types occur in every buffer |

Model builders in `models/`: `build_ocdfg(DFSnapshot)`,
`build_df2(DFSnapshot, activities, divergent)`, `build_totem(...)`,
`DF2InductiveMiner().mine(...)` + `annotate(...)` for process trees.

## Example 1: an algorithm from existing blocks

A *divergence-aware OC-DFG*: an OC-DFG that drops the arcs of an object type
when both activities diverge for that type (the arcs the DF2 miner ignores).
It combines the object tracker, the directly-follows counters and the
divergence index:

```python
from collections.abc import Mapping
from typing import Any

from ocelescope import OCEL, DirectlyFollowsGraph
from pydantic import BaseModel

from ocelescope_module_streaming.algorithms import compare_ocdfgs
from ocelescope_module_streaming.blocks import DFSnapshot, DirectlyFollowsCounters, DivergenceIndex, ObjectTracker
from ocelescope_module_streaming.catalog import ARCS_BOUND, ENDPOINTS_BOUND, BufferSpec, NoParams, register_algorithm
from ocelescope_module_streaming.framework import Buffer, BufferConfig, StreamingAlgorithm, run
from ocelescope_module_streaming.models import build_ocdfg
from ocelescope_module_streaming.ocel import ocel_stream
from ocelescope_module_streaming.stream import Event, StreamItem, StreamOptions

BUFFERS = (
    BufferSpec("objects", "Objects", "The last activity of every open object. Grows with the number of objects."),
    BufferSpec("arcs", "Arcs", "Directly-follows relations with their frequencies.", bounded_by=ARCS_BOUND),
    BufferSpec("starts", "Start activities", "Start activities per object type.", bounded_by=ENDPOINTS_BOUND),
    BufferSpec("ends", "End activities", "End activities of evicted objects.", bounded_by=ENDPOINTS_BOUND),
    BufferSpec("divergence", "Divergence index", "First full object set per activity, type and typed set."),
    BufferSpec("divergent", "Divergent pairs", "Activity–type pairs found to diverge.", bounded_by=ENDPOINTS_BOUND),
)
EVENTS_ONLY = StreamOptions(events=True, object_to_object=False, attribute_updates=False)


def without_divergent_arcs(snapshot: DFSnapshot, divergent: frozenset[tuple[str, str]]) -> DFSnapshot:
    arcs = {
        (a, b, t): n for (a, b, t), n in snapshot.arcs.items() if not ((a, t) in divergent and (b, t) in divergent)
    }
    return DFSnapshot(arcs=arcs, starts=snapshot.starts, ends=snapshot.ends)


def offline_reference(ocel: OCEL) -> DirectlyFollowsGraph:
    """The model of the complete log, here: the same algorithm without eviction."""
    with ocel_stream(ocel, EVENTS_ONLY) as stream:
        return run(DivergenceAwareOCDFG(NoParams()), stream)


@register_algorithm(
    key="example_divergence_aware_ocdfg",
    label="Divergence-aware OC-DFG",
    description="An OC-DFG without the arcs of object types that diverge on both activities.",
    buffers=BUFFERS,
    stream=EVENTS_ONLY,
    offline=offline_reference,
    compare=compare_ocdfgs,
)
class DivergenceAwareOCDFG(StreamingAlgorithm[DirectlyFollowsGraph]):
    """ObjectTracker → DirectlyFollowsCounters, plus a DivergenceIndex."""

    def __init__(self, params: BaseModel, config: Mapping[str, BufferConfig] | None = None) -> None:
        super().__init__(config)
        self._buffers = self.create_buffers(*(spec.name for spec in BUFFERS))
        objects, arcs, starts, ends, divergence, divergent = self._buffers
        self.tracker = ObjectTracker(objects)
        self.directly_follows = DirectlyFollowsCounters(self.tracker, arcs, starts, ends)
        self.divergence = DivergenceIndex(divergence, divergent)

    @property
    def buffers(self) -> tuple[Buffer[Any, Any], ...]:
        return self._buffers

    def update(self, item: StreamItem, position: int) -> None:
        if isinstance(item.x, Event) and item.x.relations:
            self.tracker.update(item.x, item.t)
            self.divergence.update(item.x)

    def finish(self, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:
        self.tracker.finish(buffer, key, value)  # records the end activity of an evicted object
        self.divergence.finish(buffer, key, value)  # forgets an evicted index entry

    def model(self) -> DirectlyFollowsGraph:
        snapshot = without_divergent_arcs(self.directly_follows.snapshot(), self.divergence.snapshot())
        return build_ocdfg(snapshot)
```

What `register_algorithm` needs:

- `key`, `label`, `description`: the catalog entry. The key is stored in run
  configurations; do not rename it later.
- `buffers`: one `BufferSpec(name, label, description, bounded_by)` per
  buffer, in eviction order. The names are what `create_buffers`,
  `RunConfig.buffers` and the frontend use; labels and descriptions are shown
  in the form (say in the description what the buffer's size grows with).
  Set `bounded_by` for buffers whose size is bounded by the log's vocabulary,
  e.g. `ARCS_BOUND`, `ENDPOINTS_BOUND` or `ACTIVITIES_BOUND` from
  `catalog`: the frontend collapses them and the quick setup skips them.
- `stream`: the item kinds the algorithm consumes by default.
- `offline(ocel)`: the reference model of the complete log. Prefer an
  independent implementation (e.g. `ocdfg_miner`, `offline_df2`,
  `offline_totem`): then "unbounded run equals offline" tests the blocks too.
  Running the algorithm itself without eviction, as above, is a fallback that
  only measures the effect of eviction.
- `compare(streaming, reference)`: a mapping from element kind to
  `ElementScores`, e.g. via `ElementScores.from_sets(found, expected)`.
- `params`: a pydantic model of the algorithm's parameters (default:
  `NoParams`).
  The algorithm receives the validated instance as `params`; its JSON schema
  renders the form.

Run it on the surgery example of Mühlmeyer et al. (2026): surgery diverges
for doctors, so doctor D2's surgery → surgery arc disappears:

```python
from datetime import UTC, datetime, timedelta

from ocelescope_module_streaming.stream import ObjectRef, Relation


def surgery(doctor: str, patient: str, day: int) -> StreamItem:
    relations = (Relation(ObjectRef(doctor, "doctor")), Relation(ObjectRef(patient, "patient")))
    return StreamItem(Event("surgery", relations), datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=day))


surgeries = [surgery("D1", "PatA", 0), surgery("D2", "PatB", 1), surgery("D2", "PatC", 2)]
model = run(DivergenceAwareOCDFG(NoParams()), surgeries)
assert not any(edge.source and edge.target for edge in model.edges)  # no arcs left
```

It is also available through the catalog, with any heuristic on any buffer:

```python
from ocelescope_module_streaming.runs import BufferSetting, RunConfig, prepare_run

config = RunConfig(
    ocel_id="unused",
    algorithm="example_divergence_aware_ocdfg",
    buffers={
        "objects": BufferSetting(capacity=1, heuristic="lru"),
        "divergence": BufferSetting(heuristic="max_age", heuristic_params={"age": 2000}),
    },
)
prepared = prepare_run(config)
run(prepared.algorithm, surgeries)
```

## Example 2: a new block

A block owns buffers that its algorithm creates, reacts to stream items or to
another block, and offers a snapshot. This one keeps the mean time per
directly-follows step, listening to an `ObjectTracker`:

```python
from dataclasses import dataclass

from ocelescope_module_streaming.blocks import Arc, Retired, Transition


@dataclass(frozen=True, slots=True)
class DurationSum:
    count: int
    seconds: float


class ArcDurations:
    """Mean seconds between the events of an object, per arc (a, b, object type).

    Args:
        tracker: The object tracker to listen to.
        durations: Buffer of `DurationSum` per arc.
    """

    def __init__(self, tracker: ObjectTracker, durations: Buffer[Arc, DurationSum]) -> None:
        self.durations = durations
        tracker.subscribe(self)

    def on_transition(self, transition: Transition) -> None:
        if transition.previous is None or transition.previous_time is None:
            return
        key = (transition.previous, transition.activity, transition.obj.type)
        seconds = (transition.time - transition.previous_time).total_seconds()
        current = self.durations.get(key) or DurationSum(0, 0.0)
        self.durations.put(key, DurationSum(current.count + 1, current.seconds + seconds))

    def on_retired(self, retired: Retired) -> None:
        pass

    def snapshot(self) -> dict[Arc, float]:
        return {arc: total.seconds / total.count for arc, total in self.durations.items()}
```

Wire it into an algorithm like any other block. Here, a minimal OC-DFG that
also reports durations:

```python
class TimedOCDFG(StreamingAlgorithm[DirectlyFollowsGraph]):
    """ObjectTracker → DirectlyFollowsCounters and ArcDurations."""

    def __init__(self, params: BaseModel, config: Mapping[str, BufferConfig] | None = None) -> None:
        super().__init__(config)
        self._buffers = self.create_buffers("objects", "arcs", "starts", "ends", "durations")
        objects, arcs, starts, ends, durations = self._buffers
        self.tracker = ObjectTracker(objects)
        self.directly_follows = DirectlyFollowsCounters(self.tracker, arcs, starts, ends)
        self.durations = ArcDurations(self.tracker, durations)

    @property
    def buffers(self) -> tuple[Buffer[Any, Any], ...]:
        return self._buffers

    def update(self, item: StreamItem, position: int) -> None:
        if isinstance(item.x, Event) and item.x.relations:
            self.tracker.update(item.x, item.t)

    def finish(self, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:
        self.tracker.finish(buffer, key, value)

    def model(self) -> DirectlyFollowsGraph:
        return build_ocdfg(self.directly_follows.snapshot())


algorithm = TimedOCDFG(NoParams())
run(algorithm, surgeries)
assert algorithm.durations.snapshot() == {("surgery", "surgery", "doctor"): 86400.0}
```

Create all buffers in one `create_buffers` call: it checks the configuration
against exactly these names, so a misspelled buffer in a run configuration is
reported.

### Rules for blocks

- **All state goes into buffers** that the algorithm creates, never into
  plain dicts that grow with the stream — otherwise heuristics cannot bound
  it. Small fixed-size bookkeeping (per type, per activity) is fine.
- **Only read keys you also write** in the same item (as `ArcDurations` reads
  and then writes the arc's sum). Then the exactness guarantee holds: if no
  key is evicted too early, the result equals the unbounded run
  (`rem:exactness`).
- **Record contributions on eviction.** If evicting a key would lose model
  information, move it into the model in `finish` — as `ObjectTracker` emits
  `Retired` and `DirectlyFollowsCounters` records the end activity. If you
  keep observations in an observation log (`Buffer.append`), the model *is*
  the buffer content; evicting shrinks the model by design.
- **Use `discard` for dependent entries** (e.g. `DivergenceIndex` discards
  all index entries of a pair once it diverges). Discards notify the
  heuristic but do not call `finish`.
- **Return immutable snapshots** (frozen dataclasses, copied dicts), so a
  model never changes behind the caller's back.
- **No Ocelescope imports** in blocks; model builders in `models/` convert
  snapshots into resources.

## Models as Ocelescope resources

The model should be an Ocelescope `Resource`, so the run can save it to the
session and the frontend can render it with no extra code:

- Reuse `DirectlyFollowsGraph` or `PetriNet` where they fit.
- Otherwise add a `Resource` subclass in `models/` with a `visualize()`
  method (see `DF2Graph`, `OCPT`, `Totem`) and **add it to
  `models.RESOURCES`**, which the module registers with Ocelescope. Without
  that, stored models of the new type cannot be loaded.

## Making it permanent

1. Put the algorithm in `algorithms/` and **import it in
   `algorithms/__init__.py`**. The catalog loads that package on first use.
2. Add blocks to `blocks/` and export them from `blocks/__init__.py`.
3. Add the definitions (blocks, model construction) to `docs/definitions.tex`.
4. Optionally add a preset to `runs/presets.py`.
5. Add tests (patterns in `tests/test_blocks.py`, `tests/test_df2.py`,
   `tests/test_ocpt.py`, `tests/test_liss_models.py`):
   - the blocks on the paper examples (`surgery_stream`, `order_stream`),
   - **unbounded run equals the offline reference** on `container_logistics`,
   - a bounded run with a heuristic, checking what is lost,
   - the resource round trip (`Model.model_validate(model.model_dump())`) and
     `visualize()`.
6. Run `pnpm run check:backend` and `pnpm run build:modules`.
