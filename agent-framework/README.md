# Agent Framework

This independently installable distribution exposes `agent_framework` using a
`src/` layout. Its version has one source: `[project].version` in `pyproject.toml`.
Read the installed version with `importlib.metadata.version("agent-framework")`.
There are no runtime dependencies at M0.

The M0 modules document the authoritative package boundaries; semantic behavior
starts in later milestones. Bindings remain independent distributions in the peer
`bindings/` directory and will be discovered through installed entry points.

Use the development container and commands in the [workspace README](../README.md).
Within an environment containing the pinned development tools, install and check
this distribution independently:

```bash
python -m pip install --no-build-isolation --no-deps -e .
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src/agent_framework tests
```

Do not set `PYTHONPATH` to `src/`. Packaging tests build and install a wheel into a
clean environment, and check that an uninstalled checkout cannot supply imports.

