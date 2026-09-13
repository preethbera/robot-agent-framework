# M3 Progress

Status: **In progress**.
Version remains **0.1.0**. M4 and later milestones are out of scope.

## Implementation subtasks

Each implementation subtask will receive focused tests, a progress update, and
a commit when stable.

1. **Endpoint and QoS descriptions** — topic/service/action kinds, roles,
   interface references, endpoint names/templates, and QoS validation.
2. **Binding realization and override validation** — Channel-to-interface-part
   mappings, multiple endpoints per Capability, allowed overrides, and protection
   of mandatory binding requirements.
3. **Deterministic manifest builder** — combine resolved semantics and binding
   descriptions; retain versions, dependencies, adapters, runtime factories,
   internal communication, lifecycle requirements, and instance templates;
   write `build/agents/<agent-id>/ros2_realization.json`.
4. **External test binding and acceptance** — direct Property topic,
   request/response service, sensing output stream, multi-endpoint Capability,
   invalid override rejection, and deterministic generation. Reuse existing
   interfaces; generate custom interface artifacts only if a test requires them.
5. **Final verification** — full M3 acceptance plus existing regressions and
   repository checks; confirm version `0.1.0` and stop after M3.

## Review findings

- M3 requires allowed Agent Definition ROS2 overrides and binding-owned mappings.
- `docs/design/ROS2 Realization.md`, sections 3 and 7, assigns mapping ownership
  to bindings and prohibits invalid overrides of mandatory requirements.
- M2 currently represents `BindingDefinition.ros2_template` and
  `AgentDefinition.ros2_overrides` as `Mapping[str, object]`. The loader validates
  only the outer `ros2.overrides` mapping. ROS2 modules are reserved stubs.

## Approved decision

The user supplied the v0.1.0 override contract. It is recorded in
`docs/design/ROS2 Realization.md`, section 7. Overrides target an exposure alias
and endpoint ID, can change only explicitly permitted names/QoS fields, and must
satisfy binding requirements after application. All invalid overrides fail the
build with resolution errors. The previous blocker is resolved.

## Checkpoints

- Planning checkpoint: `b8afa46`.
- Contract documentation updated; implementation resumed.
- Focused tests and final acceptance/regressions pending.

### Subtask 1 — complete

- Implemented endpoint descriptions, kind/role/interface validation, safe name
  templates, and validation of the explicitly supported QoS fields.
- Focused verification: 27 endpoint/QoS tests passed; scoped Ruff and strict mypy
  passed. Tests use the pinned tools in `/tmp/m3-venv` with host `PYTHONPATH`
  removed to avoid unrelated ROS pytest plugin injection.
- Documented the approved override contract and description encoding.

### Subtask 2 — complete

- Added binding endpoint permission lists and exact mandatory name/QoS
  requirements, checked before and after overrides. Immutable fields cannot be
  overridden; malformed values and violations raise resolution errors.
- Added stable qualified IDs and Channel mapping validation for all endpoint
  kinds and roles, including action goal/feedback/result/cancel.
- Focused verification: all 55 ROS2 unit tests passed (28 new); scoped Ruff and
  strict mypy passed. Unknown global override targets will be checked by the
  manifest builder in subtask 3.
