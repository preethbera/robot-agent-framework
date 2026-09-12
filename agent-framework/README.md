# Agent Framework

This independently installable distribution exposes `agent_framework` using a
`src/` layout. Its version has one source: `[project].version` in `pyproject.toml`.
Read the installed version with `importlib.metadata.version("agent-framework")`.
There are no runtime dependencies at M0.

M1 implements the technology-independent model in `model/`; other modules retain
their documented boundaries for later milestones. Bindings remain independent distributions in the peer
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

## Core model (M1)

`agent_framework.model` exposes Agent, Property, Capability, Channel, Constraint,
Group, and PayloadSchema, their supporting enums, and explicit `validate_*`
functions. The types are slotted dataclasses. Construct the model first, then call
`validate_agent(agent)` at build time; invalid models raise `ValueError`.
Construction does not run validation, discovery, or other pipeline stages.

Agent holds Channels; Properties and Capabilities reference those Channels by ID.
Groups contain mixed Property/Capability IDs and references to nested Groups.
ConstraintTarget uses a typed element reference and an optional tuple of nested
record field names for Property/Channel payload fields. These are internal Python
structures; M1 does not define or change any serialized Agent Definition grammar.
Constraint parameters are preserved without inventing an expression language.

PayloadSchema describes scalars, records, arrays, sequences, enums, and opaque
payloads. `validate_constant` checks contract-static Property values at build time;
it must not be called in the per-message hot path. Missing `constant_value` is
distinct from explicit values such as `False`, `0`, or an opaque `None`.
Semantic metadata (including units and frames) remains technology-independent.

Mappings and payload values remain caller-owned: frozen dataclasses do not deep
freeze those containers. Finish assembling them before validation and revalidate
after any edits. Opaque payloads are neither inspected nor copied by the model.
