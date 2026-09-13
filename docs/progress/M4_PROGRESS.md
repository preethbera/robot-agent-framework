# M4 Progress

Status: **Complete — M4 acceptance and regressions passed**.
Version remains **0.1.0**. M5 is out of scope.

## Planned subtasks

Each implementation subtask will receive focused tests, a progress update, and
a stable checkpoint commit.

1. **Artifact-driven Python API generation** — consume and verify the resolved
   Agent Model and finalized ROS2 realization together; generate typed Property,
   invocation, session, and Channel access under `build/agents/<agent-id>/python/`.
2. **Generic runtime abstractions** — implement the documented Property,
   invocation, session, and output/feedback/result contracts, bounded caches and
   queues, timeouts, and structured errors.
3. **ROS2 runtime integration** — construct endpoints from the finalized
   manifest, share context/executor resources, connect directly to existing
   endpoints, and support the documented optional binding factory contract.
4. **Acceptance and regressions** — exercise the generated API against the
   external test binding with an application importing no ROS/PX4 classes;
   verify Property, invocation, sensing stream, and absence of definition
   parsing in message paths. Run the complete regression and static checks.

## Completed inspection

- Read `docs/CODING_AGENT_PROMPT.md` and the M4 milestone.
- Inspected the workspace file inventory, current generation/runtime stubs, and
  generated M3 model and realization. The working tree was clean on entry.
- Verified the M3 model hash, binding lock, and `0.1.0` schema versions agree.
- Verified all three custom interface artifacts match their manifest contents.
- The test realization contains four endpoints and five Channel mappings:
  a Property subscription, command service client, sensing subscription, and
  application-owned liveness publisher.

## Documentation checkpoint resolved

- Initial inspection checkpoint: `539c08b`.
- The user authorized `docs/design/Python API Runtime and Deployment.md` as the
  M4 design authority; it has now been read.
- Its artifact pipeline, application boundary, shared ROS2 infrastructure, and
  instance registry requirements agree with the inspected M1–M3 implementation.
- Section 3 explicitly allows generated Python syntax to evolve during
  implementation. Choosing that syntax is therefore not a blocker.

## Factory decision resolved

The user supplied the factory inputs, Channel registration, lifecycle, and
resource ownership contract. It is recorded in the authorized runtime design.
Checkpoint `388442c` records the superseded blocker. Implementation proceeds
with ordinary local choices made autonomously.

## Implementation order

The runtime abstractions are the generator's import dependencies, so implement
those first, then artifact-driven generation, ROS2 integration, and acceptance.
The four planned subtasks retain their scope; only dependency order changes.

## Checks and acceptance

- M3 artifact integrity checks: **passed at the initial checkpoint**.
- Authorized runtime design and existing binding/factory code reviewed.
- Runtime, generation, and ROS2 integration implemented and focused checks passed.
- M4 full canonical acceptance and regressions: **passed** (see final checks below).
- No version changes or M5 work.

### Generic runtime checkpoint — complete

Commit: `048f4c5`.

- Implemented bounded FIFO Channels (overflow is a structured error), one-value
  Property caches, typed input/output handles, scoped invocation/session handles,
  runtime-local instance registration, and component cleanup in reverse order.
- Internal factory context carries the approved inputs and Channel registration/
  delivery callbacks; concrete ROS2 services are wired in the transport subtask.
- Local choices: blocking typed reads with finite per-read timeouts; sessions may
  remain open until explicitly closed. One active operation per Capability per
  instance avoids inventing correlation for uncorrelated native topic streams.
  Late correlated results are discarded after their operation closes.
- Focused checks: 7 runtime tests passed, including bounded queues, blocked-reader
  shutdown, startup rollback, duplicate identities, and late-result isolation.
  Scoped Ruff and strict mypy passed.

### Artifact-driven generator checkpoint — complete

Commit: `d9411a8`.

- Generator requires both finalized artifacts, validates their identity/hash,
  versions, Channel coverage, and custom interface content, and writes an
  importable typed package under the Agent build directory's `python/` tree.
- Generated API: `Agent.temperature.get()`, writable Property `.set()` where
  declared, `Agent.command.invoke(value)`, and scoped Capability `.start()`
  handles with typed input `.send()` and output/feedback/result `.read()`.
- Record payloads use generated dataclasses; scalar/sequence converters and
  payload/range/allowed-value checks are static generated code. No schema
  interpretation, reflection, or YAML parsing is added to message callbacks.
- The original manifest supplies every endpoint, mapping, factory, and QoS.
  Preconditions and mutual exclusion metadata remain declarative; no new
  expression language or technology-specific safety behavior is invented.
- Opaque payloads and outbound collections of records require an explicit binding
  adapter because native element construction is binding-specific. Those cases
  fail generation clearly if the necessary adapter is absent.
- Focused verification: 14 generation/runtime tests passed. Scoped Ruff and
  strict mypy passed, including strict mypy on the generated test Agent package.

### ROS2 runtime integration checkpoint — complete

Commit: `d08816b`.

- Implemented shared context/executor ownership, runtime-local registration,
  manifest endpoint names/QoS, direct topic/service/action clients and servers,
  static codecs/adapters, and scoped subscription/server cleanup.
- Code-backed factories receive resolved configuration, binding realization,
  instance identity/namespace, and shared services. The services' runtime object
  supplies runtime identity. Component scopes provide fallback cleanup even when
  factory creation fails; startup and normal shutdown release components in
  reverse order before shared infrastructure.
- Operation state and queues are bounded; native results are correlated to the
  operation that created them. Explicit action cancellation Channels request
  native cancellation. Closing a handle releases local resources; it does not
  invent technology-specific stop commands or implicitly cancel physical work.
- Native topic streams connect for the duration of a session. Service/action
  servers accept one request per scoped operation. Multi-Channel messages are
  assembled from declared mappings before publication or request dispatch.
- Generated payloads remain Python scalars, dataclasses, and typed collections.
  Invalid schemas, unsafe native field names, and generated member collisions
  fail at generation. Empty record cancellation payloads generate valid code.
- Added external binding fixtures and real ROS2 application tests for Property,
  invocation, sensing/liveness, native actions (feedback/result/cancellation),
  service/action servers, factory startup rollback, and factory creation cleanup.
- Added the pinned standard ROS2 `example_interfaces` package to the canonical
  image for native action tests; existing interfaces are reused unchanged.
- Focused canonical Jazzy checks: **21 passed**. Host regressions: **304 passed,
  3 ROS2 tests skipped** (all three ran successfully in the canonical focused
  suite). Ruff lint/format and strict mypy of 84 source files passed. Generated
  test Agent API regenerated from the existing M3 artifacts.
- No architecture conflicts found; version remains `0.1.0`.

### Acceptance and regression checkpoint — complete

Canonical environment: Ubuntu 24.04, Python 3.12, ROS2 Jazzy, full workspace
bind-mounted into `agent-framework-dev:latest`.

Command: `docker run --rm --mount type=bind,source="$PWD",target=/workspace/project
agent-framework-dev:latest bash docker/check.sh` (run from the workspace root).

- Full suite: **307 passed**, no skips, including all M1–M3 regressions and real
  M4 ROS2 transport/factory tests.
- Ruff lint: **passed**. Ruff formatting: **84 files passed**.
- Strict mypy: **84 source files passed**.
- Generated `build/agents/test_agent/python/agent_test_agent` from the existing
  M3 artifacts; strict mypy on that generated package: **passed**.
- Installed framework/test binding versions and all three existing M3 artifact
  schema versions: **0.1.0**.

| M4 acceptance criterion | Evidence | Result |
| --- | --- | --- |
| Application imports no ROS-specific API | AST import check; `m4_application.py` imports only generated Agent API and `time` | Passed |
| Property through generated API | Two isolated instances read native published values | Passed |
| Invocation through generated API | Native service request/result; constraints, timeout, and late-result isolation | Passed |
| Sensing stream through generated API | Native stream reads, liveness sends, bounded overflow, session reopen | Passed |
| No Agent Definition parsing per message | Runtime test disables parser, discovery, resolver, schema validation, and generation before running application | Passed |

Additional native action feedback/result/cancellation, service/action server,
factory creation/startup rollback, reverse shutdown, and resource cleanup checks
passed. No unresolved blockers or architecture issues. M4 is complete; no M5
implementation was started.
