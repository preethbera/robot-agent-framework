# M5–M7 review checkpoint

Reviewed baseline: `652d02c`, against M4 checkpoint `68b0e2c`.
Version remains `0.1.0`. Review/corrections are **complete**, checkpoint `846c357`.
The initial findings below are retained as audit history; see final validation.

## Initial contract blocker (resolved by owner decision)

M6 explicitly requires per-instance binding configuration. Sections 5–6 of
`docs/design/Python API Runtime and Deployment.md` require binding packages to
validate binding-specific instance keys. The existing BindingDefinition schema,
however, configures build-time semantics and ROS2 realization; it is not a
declaration of which values may safely change after generation.

Commit `188c858` introduced instance overrides; `decb899` restricted them through
`runtime_parameters`; `ccb312e` removed that mechanism entirely, without updating
the architectural requirement. The current deployment loader silently discards
`config.bindings`, including `arm: {target_system: 2}`. Reproduced in the pinned
PX4 image: the parsed AgentInstance contains only id, agent, and namespace.

Required decision: the external binding contract for declaring and validating
runtime-only instance parameters, and carrying that declaration through finalized
artifacts. Reusing all build-time configuration at runtime would permit changing
semantics/endpoints after generation. Silently omitting configuration does not
meet M6. No replacement contract has been invented during this review.

## Other concrete findings to address after the decision

- M6's acceptance test checks identities, namespaces and registry membership but
  does not send distinct data through the instances to establish state/ROS2
  isolation. Its node-name assertion can operate on an empty list.
- Deployment imports mutate global sys.path and reuse cached module names, so
  changing build roots can select previously loaded generated code.
- Deployment shutdown iterates creation order rather than reversing it.
- M7 subscribes to a Vector3 containing externally supplied metrics; it does not
  implement the required latency, queue-depth or dropped-sample instrumentation.
  Its test publishes hardcoded values.
- M7's PX4 checks are attribute-existence assertions, not SITL state/control.
  The embedded worker combines ROS2 publisher code and application code; it does
  not establish the stated application import boundary. Sensor coverage sends an
  empty scan and does not exercise high-bandwidth behavior or overflow.
- The performance adapter creates a new Python class per message and returns
  that object instead of the generated public payload class. Missing fields in
  adapters silently default to plausible healthy/zero values.
- The optional PX4 image/check does not install the lidar distribution. The
  generic check skips M7 when px4_msgs is absent. Thus neither route currently
  establishes full M7 acceptance. Lidar packaging references a missing README.
- M6/M7 progress files contain stale implementation/naming claims and overstate
  acceptance evidence.
- Final core runtime, generator, and BindingDefinition source have no net changes
  from M4; earlier-layer test/test-binding changes include unnecessary formatting
  churn. Subsequent functional review and corrections are recorded below.

## Baseline validation (2026-09-14)

Existing `agent-framework-px4:0.1.0` image, complete workspace bind mount:

- `bash docker/check-px4.sh`: **326 passed, 1 error**, 88.35 seconds, no skips.
  Both M5 real SITL ownership scenarios passed. M7 fails resolving the missing
  installed `lidar` binding. Script exits before static checks.
- Static checks run separately with lidar source included:
  Ruff **13 errors**; format check **23 files need formatting**;
  strict mypy **passed, 102 source files**.
- No implementation changes made after identifying the contract blocker.
  Only this resumable review record was added; no new commit was created.

## Authorized corrections

The owner approved a separate instance-configuration contract after this initial
checkpoint. Implemented `instance_configuration_schema`, carried in the finalized
ROS2 manifest and compiled into generated validators. Instance values are copied,
validated before Agent resources start, and passed separately to factories.
PX4 target_system/target_component are the concrete use case; no build-time
semantics, realization, or BindingSpec configuration is mutated.

Other corrections:

- Explicit generated file loading with temporary unique module registration and
  cleanup; no sys.path changes or cached-module reuse across build roots.
  Explicit Agent factories let applications use their imported generated payload
  classes without duplicate nominal types.
- Strict Deployment parsing and reverse shutdown/rollback, tested including
  repeated calls and failure during startup.
- M6 acceptance now sends ten distinct rounds of native ROS2 values through two
  same-definition instances and one heterogeneous instance in a shared runtime.
- Replaced injected LiDAR performance values with actual generic bounded Channel
  statistics. Sensor/PX4 code remains in its own independent binding. Latency
  measures delivery queue residence, not source acquisition/network latency;
  drop counts describe the delivery queue, not unobservable DDS loss.
- LiDAR status conversion rejects malformed input; no dynamic per-message classes
  or silent healthy defaults. Native LaserScan decoding returns generated types.
- Combined M7 test separates the ROS2 fixture from application source and exercises
  two 4096-range/20 Hz streams while actual SITL system 2 accepts arm/disarm and
  publishes corresponding state. It measures queue latency, deliberately causes
  bounded overflow and verifies recovery in a new session.
- Shared SITL test fixture removes duplicate process/log/cleanup code from M5/M7.
  No extra middleware or runtime plugin infrastructure introduced.
- Fixed packaging, Docker installation/check coverage, progress/naming claims,
  lint and formatting. Standard local wheel build directories are ignored.

Validation so far: first full pinned check **347 passed, zero skips**, 103.49 s;
strict mypy passed 108 source files; generated sensor/PX4 API strict typing passed;
local wheel builds for framework/PX4/LiDAR passed with index/dependencies disabled.
Generic ROS2 check **344 passed, 3 explicit SITL skips**, 23.35 s.
Final rebuilt-image regression after extracting the shared SITL fixture passed (below).

The rebuilt-image check initially attempted to reinstall a root-owned editable
LiDAR distribution as the non-root runtime user. Corrected: installation belongs
to Docker build; check-px4 verifies the installed version and runs acceptance.
The optional image builds successfully with exact existing firmware/interface
pins and explicit LiDAR build-context inclusion.

## Final validation

- Corrections checkpoint: `846c357`.
- Rebuilt `agent-framework-px4-review:0.1.0` from `docker/Dockerfile.px4` with
  existing exact firmware/interface/bridge pins; no vendored dependencies.
- Final full check in that image: **347 passed, zero skips, 102.01 seconds**.
  M0–M4 regressions, both M5 flights, real M6 data isolation and combined M7 all pass.
- Ruff lint and format: **passed, 109 files**. Strict mypy: **passed, 109 files**.
- Generated combined API: strict mypy **passed, 1 file**.
- Generic Ubuntu 24.04/ROS2 Jazzy check: **344 passed, 3 explicit SITL skips**,
  23.35 seconds. Generic check does not claim SITL acceptance.
- Local wheel builds: framework, PX4 binding and LiDAR binding **passed**, all
  `0.1.0`, with `--no-index --no-build-isolation --no-deps` and explicit local paths.
- Scope: native ROS2 synthetic LaserScan source, not physical LiDAR hardware;
  actual pinned PX4 SIH SITL, not mocked PX4. Queue instrumentation measures queue
  residence and application delivery loss, not acquisition latency or DDS loss.
- No outstanding architecture blockers. No milestone beyond M7 started.
