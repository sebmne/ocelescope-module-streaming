# Streaming module documentation

Object-centric process discovery on event streams with bounded memory. The
module replays an OCEL as a stream, runs streaming discovery algorithms whose
memory lives in buffers, and lets interchangeable eviction heuristics decide
what is forgotten. The goal is to compare eviction heuristics — in particular
against FIFO, under a fixed memory budget.

| Document | For |
|---|---|
| [Architecture](architecture.md) | how the parts fit together: stream, buffers, eviction modes, run loop, blocks, algorithms, catalog, API, frontend |
| [Usage](usage.md) | running experiments in Ocelescope or from Python, tests |
| [Guide: eviction heuristics](guide-eviction-heuristics.md) | implementing and registering a new heuristic |
| [Guide: streaming algorithms](guide-streaming-algorithms.md) | building a new algorithm from blocks, writing new blocks |
| [`definitions.tex`](definitions.tex) | the formal definitions (streams, buffers, heuristics, runs, blocks, models) |

Implemented techniques:

- **Online OCPT / DF2 miner** — Mühlmeyer, van Detten, Leemans, BPMW 2026;
  Rust reference in BPM-Research-Group/scope. Algorithms `df2` and `ocpt`,
  heuristic `lifecycle`, presets `muehlmeyer2026*`.
- **Object-centric streaming discovery** — Liss, Löseke, van der Aalst,
  SMA4PM 2025; reference code in loeseke/object-centric-streaming-discovery.
  Algorithms `liss_ocdfg` and `liss_totem`, heuristics `lfuda` and
  `priority`, presets `liss2025-*`.

Known differences to the reference implementations:

| Topic | Here | Reference |
|---|---|---|
| Eviction timing | after the item is processed, for every algorithm | Liss et al. evict while inserting |
| OCPT end activities | from evicted and live objects | Rust: live objects only |
| Start/end activities in DF2 | filtered by divergence | Rust: not filtered |
| No cut in the DF2 miner | explicit `no_cut` node | Rust: activities as sibling trees |
| Lifecycle checks | after every item | Rust: every 10,000 events |
| LFU-DA | a new key gets the cache age from before the eviction it causes | Liss et al.: after |
| Liss priority policies | object-type features only (buffers mix types) | also per-object features with per-type buffers |
| Liss OC-DFG end activities | activities without outgoing arcs | plus a cycle heuristic |
| LRU | positions | Liss et al.: timestamps |
