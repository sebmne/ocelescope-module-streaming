# Usage

## In Ocelescope

```bash
pnpm run sync    # install backend and frontend
pnpm run dev     # backend on :8000, frontend on :3000
```

1. Load a log: open **Resources** and import *Container Logistics* (bundled in
   `data/`), or upload an OCEL.
2. Open **Streaming**. In the panel on the right:
   - **Preset**: fills the form with a published configuration (optional).
   - **Target model**: grouped by kind of model (process tree, DF2 graph,
     OC-DFG, TOTeM); the info icon explains the selected algorithm. The OCPT
     is generated with the inductive miner from the DF2 graph. There are two
     OC-DFG algorithms: *counts* keeps counters bounded by the log's
     vocabulary and records end activities on eviction; *Liss et al.* keeps
     one entry per observation, so its arc buffer grows with the stream and
     must be bounded too.
   - **Stream items**: events, O2O updates, attribute updates; the
     algorithm's default is preselected. Positions count every replayed item,
     so this changes position-based heuristics.
   - **Buffers**: the buffers that grow with the stream (e.g. objects) come
     first. **Quick setup** configures all of them at once; each buffer can
     then be adjusted with a switch between *Unbounded*, *Capacity*,
     *Schedule* (the heuristic decides when entries expire) and *Both*, plus
     the capacity, the heuristic and its parameters. Only modes and
     heuristics that fit together are offered. The info icon next to a buffer
     explains what it stores and what its size depends on. Buffers that are
     bounded by the log's vocabulary (at most one entry per activity or
     activity–type combination) are collapsed, since they are finite for
     every log.
3. **Start run**. The canvas shows the streaming model, the offline reference
   or both side by side; the bar above it shows F1 per element kind.
   **Details** lists precision/recall and per-buffer statistics: mode,
   capacity, peak and mean size, evictions per reason, and premature
   evictions ("evicted too early").

**Monitor buffer sizes** (below *Start run*) records the number of entries of
every buffer at 200 evenly spaced points of the run, plus the last item. The
plots appear under the metrics; a dashed grey line marks a buffer's capacity.
From Python, pass `evaluation.BufferSampler(expected_items)` as an observer
and call `sampler.finish(last_position, algorithm)` after the run.

How models are drawn:

- **OCPT**: a process tree; leaves list their object types with `con`,
  `div` and `def` markers, and a `no cut` node marks activity sets no cut
  applies to.
- **DF2 graph**: the underlying OC-DFG, one color per object type. Arcs, start
  and end activities that the DF2 graph suppresses because of divergence are
  dashed and grey; activities name the types they diverge for.
- **TOTeM**: as in Liss et al., one line per pair of connected object types.
  Each end shows the relation towards that end's type: the temporal relation
  (■ during, □ during inverse, ▶ precedes, ▷ precedes inverse, || parallel),
  the log cardinality and, in brackets, the event cardinality.

Both models are also added to the session's resources.

## From Python

The core runs without the backend. Replay a log file, configure buffers and
run:

```python
from ocelescope import OCEL

from ocelescope_module_streaming.algorithms import StreamingOCPT, compare_ocpts, offline_ocpt
from ocelescope_module_streaming.evaluation import BufferMonitor
from ocelescope_module_streaming.catalog import NoParams
from ocelescope_module_streaming.framework import BufferConfig, run
from ocelescope_module_streaming.heuristics import FIFO
from ocelescope_module_streaming.ocel import ocel_stream
from ocelescope_module_streaming.stream import StreamOptions

ocel = OCEL.read_duckdb("data/event_logs/container_logistics.db")
algorithm = StreamingOCPT(NoParams(), {"objects": BufferConfig(capacity=500, heuristic=FIFO())})
monitor = BufferMonitor()
with ocel_stream(ocel, StreamOptions(object_to_object=False, attribute_updates=False)) as stream:
    model = run(algorithm, stream, [monitor])

print(compare_ocpts(model, offline_ocpt(ocel)))
print(monitor.statistics()["objects"])
```

Or go through the catalog, exactly as the API does, e.g. with a preset:

```python
from ocelescope_module_streaming.runs import PRESETS, prepare_run

preset = next(p for p in PRESETS if p.key == "muehlmeyer2026")
prepared = prepare_run(preset.to_run_config(ocel_id="unused"))
with ocel_stream(ocel, prepared.stream) as stream:
    model = run(prepared.algorithm, stream)
reference = prepared.spec.offline(ocel)
scores = prepared.spec.compare(model, reference)
```

`prepare_run` validates the configuration against the catalog: unknown
algorithms, buffers or heuristics, invalid parameters and unsupported modes
raise `InvalidRunConfig`.

`scripts/replay_demo.py` prints a summary of a replayed log:

```bash
uv run python backend-modules/streaming/scripts/replay_demo.py data/event_logs/container_logistics.db
```

## Checks

```bash
pnpm run check:backend     # ruff, pyright, pytest
pnpm run check:frontend    # TypeScript
pnpm run build:modules     # regenerate the frontend API client after backend API changes
```

Tests worth knowing (`backend-modules/streaming/tests/`):

| Test | Guards |
|---|---|
| `test_ocdfg.py::test_fifo_bounded_output_is_unchanged` | golden output of a FIFO-bounded OC-DFG; regenerate with `UPDATE_REFERENCE=1` only for intended changes |
| `test_*::test_unbounded_equals_offline` | every algorithm without eviction equals its offline reference |
| `test_ocpt.py::test_cut_miner_matches_rust` | the cut miner reproduces the Rust miner on 801 graphs |
| `test_eviction.py` | eviction modes, scheduling, hooks and configuration validation |
| `test_fast_eviction.py` | constant-time FIFO/LIFO/LRU agree with their scores |
| `test_docs.py` | the code examples in the guides run |

`tests/support.py` builds streams in a few lines:

```python
from support import event, o2o, obj, stream_of

stream = stream_of(
    event("Place order", customer="c1", order="o1", item=["i1", "i2"]),
    o2o(obj("parcel", "p1"), obj("shipping label", "l1"), "labeled"),
)
```

Fixtures: `surgery_stream` (Mühlmeyer et al. 2026, Table 1), `order_stream`
(Liss et al. 2025, Table 1) and `container_logistics` (the bundled log).

## Reference trees of the Rust cut miner

`tests/reference/cut_miner_cases.json` holds the trees the Rust OCPT miner
(BPM-Research-Group/scope) produces for 801 DF2 graphs. To regenerate them
from a checkout of that repository (needs `cargo`):

```bash
cd backend-modules/streaming
uv run python scripts/cut_miner_reference.py /path/to/scope
```
