# M3 Progress

Status: **Blocked pending ROS2 contract clarification**.
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

## Blocker

The reviewed docs do not define the binding/Agent ROS2 override contract:

- how an override addresses a binding exposure and endpoint;
- how a binding declares which endpoint or QoS changes are permitted;
- how mandatory ROS2 requirements are represented and checked.

Choosing these rules would introduce a ROS2 design decision that the user has
explicitly reserved for review. Please provide or authorize the contract before
implementation resumes. No architectural contradiction is asserted.

## Validation and completion

- Inspection only; no implementation changes or focused tests yet.
- M3 acceptance and regressions have not run because implementation is blocked.
- No version changes or work on later milestones.
