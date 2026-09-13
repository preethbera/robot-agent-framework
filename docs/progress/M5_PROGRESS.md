# M5 Progress

Status: **In progress — compatibility decision resolved**.
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

## Compatibility decision — resolved

The user authorized selecting the pair. Selected stable **v1.16.2**:

- PX4 firmware: `54f0455ffcd755534539a7cf33a09a20bf71d29d`.
- `px4_msgs`: `392e831c1f659429ca83902e66820d7094591410`.
- Micro XRCE-DDS Agent v2.4.3: `73622810d984349b80bbac0ef55fc0b694d62222`.

The [firmware release](https://github.com/PX4/PX4-Autopilot/releases/tag/v1.16.2)
is designated stable; the [interface release](https://github.com/PX4/px4_msgs/releases/tag/v1.16.2)
explicitly matches it. The pinned firmware's Ubuntu setup supports 24.04.
Build matching interfaces with Jazzy in an external colcon environment; no
translation middleware or dependency source is added under the project tree.
Exact revisions are recorded in `docker/px4-versions.env`. This follows the
[version-matching rule](https://docs.px4.io/v1.16/en/ros2/user_guide).

## Package/catalog checkpoint

- Independent installable distribution with normal entry-point discovery and no
  ROS/PX4 imports during discovery, resolution, or generation.
- Extensible command descriptors and separate direct Property definitions;
  nine definitions cover four state Properties and five discrete operations.
- Use native VehicleCommand service request/reply correlation, not a replacement
  request/ack protocol. Acknowledgement is exposed separately from state.
- Position/velocity are local NED (metres/metres per second); named armed state
  and flight mode avoid exposing PX4 enum numbers to applications.
- Three focused catalog/conversion/pipeline tests passed; Ruff and strict mypy
  passed. Optional environment build and runtime implementation are ongoing.

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
- Catalog tests passed; runtime and SITL acceptance remain pending.
- M5 acceptance: **not passed; pending runtime implementation and SITL checks**.
