# Coding Agent Prompt

The coding workspace root is **`project/`**. Open and inspect the complete `project/` directory before changing code. Do not work with `agent-framework` as if it were the whole project.

Read `project/docs/README.md`, `project/docs/IMPLEMENTATION_READINESS.md`, both architecture documents, all design documents, and the active milestone before coding. Then implement only the requested milestone.

This is a production-grade robotics framework. The architecture is already decided for Prototype v0.1.0.

## Workspace rules

- `project/` is the grand development workspace and must contain the framework, locally developed bindings, Agent Definitions, Deployment Specifications, generated artifacts, cross-component tests, Docker environment, and project documentation.
- `project/agent-framework/` is one independently installable Python distribution. Its import package is `agent_framework`.
- `project/bindings/<binding>/` contains independently installable binding distributions. Do not move binding implementations into `agent-framework`.
- Local bindings must be installed/discovered like normal packages. Do not make the framework scan `project/bindings/` or import bindings directly by filesystem path.
- Reusable Agent Definitions live under `project/agents/`.
- Runtime instance configuration lives under `project/deployments/`.
- Generated outputs belong under `project/build/`, not inside source packages.
- Workspace Docker configuration belongs under `project/docker/` and must mount the complete workspace.

## Non-negotiable architecture rules

- Do not introduce `Data`, `Information`, `Observation`, `Telemetry`, or any other third primitive. The only primitives are `Property` and `Capability`.
- `Property` represents information about the Agent itself or one of its components.
- Sensor acquisition is modeled as a Capability. Sensor measurements are delivered through Capability output/result/feedback Channels.
- Do not rename core concepts without an explicit architecture change request.
- Do not use Pydantic.
- Treat the explicit file-level framework layout in `project/docs/design/Environment and Repository.md` as authoritative. Do not collapse planned modules into placeholder directories or invent a different package structure without an explicit architecture change request.
- Follow the required sequence: Agent Definition -> Resolved Agent Model -> ROS2 Realization -> Python API Generation.
- The Python API must not be generated directly from the Agent Definition.
- Reuse existing ROS2 interfaces when correct. Do not duplicate them merely to create generic names.
- A binding defines technology-specific semantics and ROS2 mappings. The framework validates/materializes those mappings rather than inventing PX4 or vendor logic.
- A code-backed binding runtime component is optional. Direct bindings may connect the Agent runtime directly to existing ROS2 endpoints without an extra adapter hop.
- Do not add parsing, package discovery, generic reflection, or schema resolution to per-message runtime paths.
- Keep runtime queues bounded and failures explicit.
- Keep all project, schema, Binding API, and handoff versions at `0.1.0` unless the project owner explicitly requests a version change. Documentation or prompt changes do not trigger a version bump.

## For every milestone

1. inspect the entire `project/` workspace first,
2. read the active milestone and its prerequisite design documents,
3. implement only that milestone and its stated prerequisites,
4. keep package boundaries intact,
5. keep interfaces typed and small,
6. add tests with implementation,
7. run the milestone's tests, Ruff, and mypy,
8. report changed files and assumptions,
9. report any architecture contradiction instead of silently redesigning it,
10. stop after the milestone acceptance criteria pass.

When ROS2 or PX4 behavior matters, verify it against official documentation for the pinned versions before implementing technology-specific behavior.
