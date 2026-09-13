# M4 Progress

Status: **Blocked on the code-backed binding runtime factory contract**.
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

## Exact remaining blocker

M4 requires optional binding runtime factory support for code-backed bindings.
The authorized design's section 4 requires code-backed runtime instances when
needed, but does not define the factory/component protocol.

Existing implementation evidence:

- `binding/definition.py` defines `runtime_factory: str | None` and requires a
  reference for `RuntimeMode.CODE_BACKED`; it defines no runtime protocol.
- `ros2/builder.py` preserves the factory reference in the finalized manifest.
- M3's factory test verifies reference preservation without importing or invoking
  the factory, using `unimportable_binding:create`.
- Generic and ROS2 runtime modules remain stubs.

The necessary external binding contract still needs to establish:

1. The factory's inputs and the resources/services made available to it.
2. The returned component interface and how it exchanges logical Channel values
   with the generic Agent runtime.
3. Component initialization, startup, shutdown, and resource ownership, including
   cleanup if creation/startup fails.

These define an interoperability and lifecycle contract between independently
installed bindings and the framework, rather than just generated Python syntax.
Implementing a guessed protocol would invent a decision the user has reserved
for review. Please provide this minimal factory/component contract before work
resumes. No architectural contradiction has been found in the inspected areas.

## Checks and acceptance

- M3 artifact integrity checks: **passed at the initial checkpoint**.
- Authorized runtime design and existing binding/factory code reviewed.
- No implementation changes; documentation diff check passed.
- M4 implementation and focused runtime tests: **not started**.
- M4 acceptance and full regressions: **not run; acceptance not yet passed**.
- No version changes or M5 work.
