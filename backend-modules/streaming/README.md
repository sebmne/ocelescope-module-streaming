# Streaming

Object-centric process discovery on event streams with bounded buffers and eviction heuristics

An [Ocelescope](https://www.ocelescope.org) backend module. It is a FastAPI app
that `ocelescope-backend` discovers through the `ocelescope_backend.modules`
entry point in `pyproject.toml` and serves under `/modules/streaming/v1`.

- `src/ocelescope_module_streaming/module.py` — module class `Streaming` (key `streaming`)

Install it next to `ocelescope-backend` (e.g. as a uv workspace member of an
Ocelescope module project) and run `ocelescope-backend serve`.

## Updating from the template

This module was generated with [Copier](https://copier.readthedocs.io). To pull
in later changes from the template, commit your work and run in this folder:

```sh
uvx copier update
```
