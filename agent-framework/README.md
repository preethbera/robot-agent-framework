# Agent Framework

This independently installable distribution exposes `agent_framework` using a
`src/` layout. Its version has one source: `[project].version` in `pyproject.toml`.
Read the installed version with `importlib.metadata.version("agent-framework")`.
There are no runtime dependencies at M0.

M1 implements the technology-independent model in `model/`. M2 implements
`binding/`, `definition/`, `resolution/`, and `serialization/`; other modules retain
their boundaries for later milestones. Bindings remain independent distributions in the peer
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

## Binding and resolution (M2)

Binding API `0.1.0` providers register in `agent_framework.bindings`. The entry-point
name supplies the namespace (`test` for `test.temperature`), and its zero-argument
callable returns `BindingPackage` with explicitly supported API versions. Duplicate
providers and missing/incompatible referenced definitions fail before runtime.
Dependencies are checked transitively; they do not implicitly expose functionality.

`BindingRequirements` separates mandatory Constraints/Channels from defaults that
configuration may change. Constraint range limits use `min`/`max`; allowed values
use `values`. Added compatible constraints narrow existing limits; mandatory
limits cannot be weakened and empty intersections fail. Preconditions and mutual
exclusions remain declarative data without an expression evaluator.

Resolved Channel/Constraint IDs use `exposed_alias.local_id`. Constraint string
targets identify model elements; an optional `parameters.field` names a literal
record field. Payload limits on a Capability require one unambiguous relevant
Channel, or an explicit Channel target. These Python representations preserve the
authoritative Agent Definition keys and do not introduce a new schema version.

Artifacts are UTF-8 JSON with sorted object keys and a trailing newline. Entity
lists are sorted by ID; byte constants are base64 in their schema-typed value slot.
The lock records the raw Agent Definition SHA-256 and installed distribution/API
versions. Technology templates, runtime factories, and ROS2 overrides are kept in
the in-memory `Resolution`, separate from serialized Agent semantics. Binding-owned
responsibilities are hidden; application-owned responsibilities are Agent metadata.

For local build tools install `python -m pip install --no-build-isolation -e '.[build]'`.
The canonical Docker image locks all build dependencies with hashes. Run the full
workspace checks in the root README to include the independent binding and system tests.
