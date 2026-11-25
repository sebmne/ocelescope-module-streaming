# Streaming

Object-centric process discovery on event streams with bounded buffers and eviction heuristics

An [Ocelescope](https://www.ocelescope.org) backend module. It is a FastAPI app
that `ocelescope-backend` discovers through the `ocelescope_backend.modules`
entry point in `pyproject.toml` and serves under `/modules/streaming/v1`.

The code follows the buffer-based framework of the paper (`paper/framework.tex`):

- `stream/` — stream items, well-formedness, and the replay of an OCEL (`stream/ocel.py`)
- `framework/` — buffers (`ins` only), heuristics over the buffer history with private buffers,
  streaming algorithms (`upd`, `emit`), runs and monitors (evictions, premature evictions, fill)
- `heuristics/` — FIFO, LRU, LFU, LFU-DA, Random, and the lifecycle heuristic
- `algorithms/` — the OC-DFG and TOTeM of Liss et al. (2025) and the paper's `A_df`
- `models/` — the OC-DFG and TOTeM resources the algorithms emit
- `api/` — catalog, presets and live replays on background threads
- `module.py` — module class `Streaming` (key `streaming`)

Run the checks with `pnpm run check:backend` from the repository root.

Install it next to `ocelescope-backend` (e.g. as a uv workspace member of an
Ocelescope module project) and run `ocelescope-backend serve`.

## Updating from the template

This module was generated with [Copier](https://copier.readthedocs.io). To pull
in later changes from the template, commit your work and run in this folder:

```sh
uvx copier update
```
