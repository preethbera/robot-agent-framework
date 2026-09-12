# M2: Binding API and Agent Resolution

## Goal

Load one declarative Agent Definition, discover external bindings, and produce a deterministic Resolved Agent Model.

## Implement

1. Binding API `0.1.0`.
2. Python entry-point based binding discovery.
3. YAML 1.2 Agent Definition loader using safe `ruamel.yaml` configuration.
4. Duplicate-key rejection and no executable YAML tags.
5. Explicit validation without Pydantic.
6. Hybrid binding/Agent authoring rules.
7. Resolver.
8. `project/build/agents/<agent-id>/resolved_agent_model.json`.
9. `project/build/agents/<agent-id>/binding_lock.json`.
10. deterministic serialization/hashing.

## Test Binding

Create a minimal test binding distribution at `project/bindings/test/`, outside framework core, with its own `pyproject.toml`, import package, and tests.

It should expose at least:

- one Property,
- one invocation Capability,
- one sensing session Capability with an output stream.

## Acceptance

- Installing `project/bindings/test/` as a normal/editable package makes it discoverable without modifying framework code or scanning the `bindings/` directory.
- Missing binding references fail clearly.
- Incompatible Binding API versions fail before runtime.
- Same inputs produce deterministic artifacts.
- Agent Definition cannot weaken mandatory binding requirements.
- No ROS2 realization is built in this milestone.
