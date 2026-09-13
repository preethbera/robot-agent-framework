# M5 Progress

Status: **Blocked at dependency compatibility target; implementation not started**.
Project, framework, and binding version remain **0.1.0**. M6 is out of scope.

## Inspection

- Started from clean M4 acceptance checkpoint `68b0e2c`.
- Read M5 and `docs/CODING_AGENT_PROMPT.md`; inspected the workspace layout,
  existing independent test binding, Binding API/configuration hooks, Channel
  model, runtime factory/lifecycle implementation, and canonical Docker setup.
- Consulted the needed design authorities: Environment and Repository, Binding
  Model, ROS2 Realization, and Python API Runtime and Deployment.
- Existing architecture supports multiple modular definitions in one installed
  binding distribution, direct state Properties, and code-backed operations.
  No framework redesign has been identified as necessary.
- The canonical Docker environment pins ROS2 Jazzy through an immutable image.
  A targeted repository search found no PX4 firmware release/revision or matching
  `px4_msgs` revision. The milestone nevertheless requires implementation
  against the pinned PX4/ROS2 versions.

## Required decision

Specify the supported PX4 firmware release/revision and matching `px4_msgs`
revision (or authorize selection of a compatible pinned pair). This establishes
the external message and flight-control compatibility target before verifying
commands, acknowledgements, mode transitions, and Offboard sequencing against
official version-specific sources. Host installations are not an authoritative
substitute for the canonical environment.

No dependency source has been downloaded, copied, or vendored into the project.

## Planned subtasks

Each stable subtask will receive focused tests, this progress update, and a
checkpoint commit.

1. **Package and compatibility environment** — independent `agent-binding-px4`
   distribution; explicit pinned external ROS/PX4 dependencies; modular catalog,
   configuration, and lazy runtime imports. Keep generic framework installation
   independent of optional PX4 dependencies.
2. **State Properties and command operations** — reusable endpoint/QoS and
   conversion helpers; position, velocity, armed state, flight mode; extensible
   command definitions for arm/disarm/land/hold/orbit, with acknowledgement
   handling separate from observable state.
3. **Offboard position session** — binding-owned sequencing, mode transitions,
   scoped resources, and declared binding/application liveness ownership;
   focused timeout, failure, and lifecycle tests.
4. **SITL acceptance and regressions** — build through resolved Agent Model and
   finalized ROS2 realization; generated-only application imports; real SITL
   control acceptance, full regressions, lint, formatting, and typing.

## Checks

- Initial working tree: clean.
- Documentation diff check: passed.
- No implementation tests or SITL acceptance run in M5 yet.
- M5 acceptance: **not passed; pending implementation and compatibility target**.
