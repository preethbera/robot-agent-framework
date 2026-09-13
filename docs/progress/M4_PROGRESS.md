# M4 Progress

Status: **Blocked on prerequisite documentation access**.
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

## Exact blocker

The user permits design/architecture files only when explicitly referenced by
`docs/milestones/M4_Python_API_and_Runtime.md`. That milestone currently contains
no design/architecture references. The broader reading instruction in
`docs/CODING_AGENT_PROMPT.md` is superseded by the user's narrower scope.

The permitted documents list features and acceptance outcomes but do not specify
the public generated API, session lifecycle/concurrency contract, or optional
binding runtime factory protocol. The corresponding implementation modules are
stubs, so they cannot establish those contracts either.

The existing `docs/design/Python API Runtime and Deployment.md` is the apparent
prerequisite, but it has not been read because it is outside the explicit reading
scope. Authorize that document (and identify any other intended prerequisites),
or add the intended references to M4, before implementation resumes.

This is a documentation-scope blocker, not an asserted architectural contradiction
or a claim that the decisions are absent from the repository. No new architecture
has been invented.

## Checks and acceptance

- M3 artifact integrity checks: **passed**.
- M4 implementation and focused runtime tests: **not started**.
- M4 acceptance and full regressions: **not run; acceptance not yet passed**.
- No version changes or M5 work.
