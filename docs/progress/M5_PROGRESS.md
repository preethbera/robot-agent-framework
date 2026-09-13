# M5 Progress

Status: **Complete**.
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
- M5 acceptance: **passed; 320 tests, Ruff, and strict mypy clean**.

## Runtime checkpoint

- Catalog/package/pins checkpoint: `fc344f2`.
- Ten modular definitions now include the Offboard position-control session.
- Implemented native command service transport, per-runtime/endpoint bounded
  command coordination, terminal acknowledgement names, and cleanup. No retry
  or forced arming; acknowledgements do not update observed Properties.
- Timeout/abandonment quarantines the command lane for that runtime, avoiding
  late response misassociation in PX4's single-pending-request service. The
  implementation uses the existing framework factory/lifecycle contract.
- Offboard implements fresh-position checks, explicit initial setpoint, full
  heartbeat warm-up, binding/application liveness, mode-request acknowledgement,
  observed active/inactive status, exclusive session ownership, and cleanup.
- Shutdown stops proof of life and leaves PX4's configured loss-of-Offboard
  policy authoritative. No implicit arming or failsafe parameter changes.
- Eight focused tests passed; scoped Ruff and strict mypy (10 files) passed.
  Real ROS2/SITL checks remain pending the isolated environment build.
- `px4_msgs` compiled successfully outside the project source tree. The pinned
  XRCE bridge and firmware environment build is ongoing.

### Runtime edge-case verification

- Runtime checkpoint: `ed3e940`.
- Late application pulses cannot conceal a missed liveness deadline; an expired
  handle cannot restart control. Timer-side native publish failures stop the
  session and report a structured transport error.
- Ten focused tests passed, including exclusive control ownership and complete
  resource release. Scoped Ruff and strict mypy passed.
- SITL acceptance application and both liveness variants are prepared. The first
  firmware build exposed an upstream shallow NuttX tag-parsing failure unrelated
  to SITL. The optional environment now fetches only SITL-required submodules and
  caches acquisition separately from compilation; upstream sources are unchanged.

## Real SITL integration checkpoint

- Edge-case checkpoint: `1178e52`.
- Optional image built successfully with exact firmware/interface/bridge pins;
  no external dependency sources were added under the project tree.
- SITL revealed two integration details, now fixed: direct state adapters receive
  native integer enum fields, and PX4 requires trajectory timestamps newer than
  position-control activation. The position component refreshes its bounded
  cached target alongside each proof-of-life publication.
- Added a direct `px4.landed` Property so the application observes actual ground
  state before ordinary disarm. This required only another modular Property
  declaration, with no framework changes. Catalog now has eleven definitions.
- The generated-only application exercised all state Properties, explicit arm,
  Offboard ascent, hold, orbit, land, and disarm against real pinned SIH SITL.
- Focused real acceptance: **3 passed in 62.47 seconds**, covering import isolation
  and complete flights with both binding-owned and application-owned liveness.
- Ten binding unit/pipeline checks passed; scoped Ruff and strict mypy passed.
- Full canonical M5 acceptance plus regressions: **passed**.

## Final acceptance

- SITL checkpoint: `fba513f`.
- The full M5 validation run exposed a race in the acceptance application: a
  liveness pulse could fire after Hold ended the Offboard session. The
  application's heartbeat worker now receives an explicit exit signal before the
  Hold command, and only tolerates `CLOSED`/`NOT_READY` errors after that signal.
  The binding runtime is unchanged; no framework modifications were required.
- Full canonical check in the pinned optional image: **320 passed in ~80 seconds**,
  covering framework unit tests, M1–M4 regressions, M5 SITL acceptance (import
  isolation plus both binding-owned and application-owned liveness flights),
  integration tests, and binding unit/pipeline checks.
- Ruff lint, Ruff format, and strict mypy: all clean across 96 source files.
- Generated API typing: clean (strict mypy, 1 source file).
- M5 acceptance: **passed**.
