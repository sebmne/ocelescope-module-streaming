# Streaming

Object-centric process discovery on event streams with bounded buffers and eviction heuristics

An [Ocelescope](https://www.ocelescope.org) backend module. It is a FastAPI app
that `ocelescope-backend` discovers through the `ocelescope_backend.modules`
entry point in `pyproject.toml` and serves under `/modules/streaming/v1`.

- `src/ocelescope_module_streaming/module.py` — module class `Streaming` (key `streaming`)

Install it next to `ocelescope-backend` (e.g. as a uv workspace member of an
Ocelescope module project) and run `ocelescope-backend serve`.

## Documentation

See [`docs/`](../../docs/README.md) at the repository root:

- [Architecture](../../docs/architecture.md) — stream, buffers, eviction modes, run loop, blocks, algorithms, API
- [Usage](../../docs/usage.md) — running experiments in Ocelescope and from Python, tests
- [Guide: eviction heuristics](../../docs/guide-eviction-heuristics.md) — how to implement a heuristic
- [Guide: streaming algorithms](../../docs/guide-streaming-algorithms.md) — how to build an algorithm from blocks
- [`definitions.tex`](../../docs/definitions.tex) — formal definitions

## Layout

| Path | Contents |
|---|---|
| `stream/` | stream items and well-formedness |
| `framework/` | buffers, heuristics interface, algorithm base class, run loop |
| `heuristics/` | built-in eviction heuristics |
| `blocks/` | reusable algorithm parts |
| `models/` | model builders and Ocelescope resources |
| `algorithms/` | registered algorithms with offline references |
| `catalog/`, `runs/`, `api/` | registries, run configuration and presets, HTTP API |
| `evaluation/` | run observers |
| `ocel.py` | replay of Ocelescope logs |
| `scripts/` | replay demo, reference trees of the Rust cut miner |
| `tests/` | `pnpm run check:backend` |

## Updating from the template

This module was generated with [Copier](https://copier.readthedocs.io). To pull
in later changes from the template, commit your work and run in this folder:

```sh
uvx copier update
```
