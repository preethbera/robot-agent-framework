# ROS2 Realization

## 1. Position in the Pipeline

ROS2 realization happens **after** the Agent Definition has been resolved.

```text
Agent Definition
    -> Resolved Agent Model
    -> ROS2 Realization
    -> Python API Generation
```

This ordering is fixed for Prototype v0.

## 2. Inputs

The ROS2 Realization Builder consumes:

- `project/build/agents/<agent-id>/resolved_agent_model.json`,
- binding ROS2 realization templates,
- binding versions and dependencies,
- optional ROS2 overrides from the Agent Definition,
- instance-independent endpoint templates.

## 3. Binding-owned ROS2 Mapping

Bindings define how their functionality maps to ROS2.

The framework does not infer PX4 or sensor-specific control semantics from generic Channels.

The framework is responsible for validating, normalizing, and materializing binding-provided ROS2 mappings.

## 4. ROS2 Endpoint Model

Supported endpoint kinds:

```text
topic
service
action
```

Every resolved ROS2 endpoint description must encode at least:

```text
id
kind
name or name_template
interface_type
role
qos optional
existing
```

Roles:

```text
topic: publisher | subscriber
service: client | server
action: action_client | action_server
```

## 5. Channel Mapping

Logical Channels may map to ROS2 interface parts such as:

```text
message
request
response
goal
feedback
result
cancel
```

Multiple Channels may map to one ROS2 service/action or to multiple endpoints behind one Capability.

## 6. Existing Interfaces First

- Reuse existing standard or technology-provided ROS2 interfaces whenever correct.
- Do not republish merely to create generic endpoint names.
- Generate a custom interface only if no existing interface can represent the required communication correctly.
- Generated interfaces are an implementation artifact, not a new semantic layer.

## 7. QoS and Overrides

Binding defaults provide the correct baseline QoS and endpoint details for that technology.

The Agent Definition may specify an allowed ROS2 override when a deployment/application has a concrete reason.

Mandatory binding requirements cannot be overridden into an invalid configuration.

### v0.1.0 override contract

- Bindings own the default ROS2 realization.
- Agent Definition overrides target a stable `<binding-instance-id>.<endpoint-id>`.
  The binding instance ID is the resolved exposure alias (`expose[].as`).
- Only endpoint name and supported QoS fields are overridable.
- Endpoint kind, ROS interface type, Channel direction/schema/mapping, binding
  runtime logic, sequencing, and mandatory requirements are not overridable.
- Binding definitions distinguish overridable defaults from mandatory requirements.
- The builder applies overrides after semantic resolution, then validates each
  final endpoint against all binding requirements.
- Unknown targets, unsupported fields, invalid values, and requirement violations
  are hard resolution errors.
- The override system must not expand beyond this scope.

## 8. ROS2 Realization Manifest

Produce deterministic `project/build/agents/<agent-id>/ros2_realization.json` containing:

```text
selected bindings and versions
ROS2 endpoints
interface types
QoS
Channel mappings
adapters/conversions
binding runtime factories
binding-internal communication requirements
startup/lifecycle requirements
namespace and instance templates
custom interface artifacts if any
```

This artifact is technology-specific.

## 9. Runtime Efficiency

The manifest must permit the runtime to connect directly to existing native endpoints when possible.

Do not require:

```text
native topic -> generic republished topic -> Agent API
```

when this is sufficient:

```text
native topic -> Agent runtime adapter -> Agent API
```

High-bandwidth sensing Capability outputs must avoid unnecessary copies and serialization hops.

## 10. v0.1.0 description encoding

Endpoint descriptions use string-valued kinds and roles from section 4. Local
endpoint IDs are identifiers without dots; the builder prefixes them with the
exposure alias. Interface types use `package/msg/Type`, `package/srv/Type`, or
`package/action/Type`, matching the endpoint kind. `existing` is an explicit
boolean. Exactly one of `name` and `name_template` is required.

Name templates accept `{agent_id}`, `{binding_instance_id}`, `{namespace}`, and
`{instance_id}`. Agent and binding IDs resolve at build time; namespace and
instance substitutions remain for deployment. Templates do not execute code or
accept attribute access, conversions, or format specifications.

The supported QoS fields in v0.1.0 are `history`, `depth`, `reliability`, and
`durability`. Policies accept `system_default`, or respectively
`keep_last|keep_all`, `reliable|best_effort`, and `volatile|transient_local`.
Depth must be a non-negative integer; `keep_last` requires positive depth.
Unspecified QoS remains unspecified; the builder does not invent technology
QoS defaults. Other QoS fields are unsupported and rejected in this version.

Each binding template contains `endpoints` and `channel_mappings` sequences.
Endpoint entries add `overridable` (a list such as `name`, `qos.depth`) and
`requirements` (exact required `name` and/or partial `qos` values) to the endpoint
fields above. An omitted permission list allows no overrides. Requirements are
checked on the defaults and after overrides; permission never bypasses them.
Immutable endpoint fields remain binding-owned by construction.

Example Agent Definition override:

```yaml
ros2:
  overrides:
    temperature.value:
      name: /native/temperature
      qos: {depth: 10}
```

Each Channel mapping names a binding-local `channel`, `endpoint`, and interface
`part`; optional `field` selects a dotted ROS message field, and optional `adapter`
names a binding-owned conversion. The builder qualifies Channel and endpoint IDs
with the exposure alias, validates references, rejects duplicate mappings, and
requires every resolved Channel to have a mapping. Roles describe the Agent
runtime's connection: a subscriber receives an Agent-to-consumer Channel; a
publisher transmits a consumer-to-Agent Channel. Service/action parts obey the
corresponding client/server directions. Bindings own payload field/schema
compatibility and conversion logic; the builder does not infer conversions or
import interface packages to introspect payloads.

`BindingDefinition.configure_ros2`, when supplied, is a build-time description
hook receiving validated configuration (defaults merged with Agent config).
Its returned template replaces the static `ros2_template`; this lets a binding
keep configuration-dependent Channels and endpoints consistent. It runs only
in the ROS2 builder, before overrides, and never changes resolved semantics.
Neither runtime factories nor adapters execute during realization.

Templates may also carry `internal_communication`, `startup`, and `lifecycle`
declarative requirements. Their order is preserved because bindings own
sequencing. The manifest retains these per binding instance, together with
configuration, dependencies, runtime mode/factory, the complete binding lock,
and a hash of the resolved model. Endpoint and mapping collections sort by
stable identifiers; no timestamps or machine-specific paths enter the manifest.

`build_realization(resolution)` builds a manifest from the in-memory resolved
model. `write_realization(resolution, workspace)` first verifies that persisted
`resolved_agent_model.json` and `binding_lock.json` match that resolution, then
writes `build/agents/<agent-id>/ros2_realization.json`. Invalid builds fail before
writing output. Individual files use atomic replacement; the manifest is
published after its interface artifacts. No Python API or runtime is generated.

Custom interfaces require explicit `custom_interfaces` entries, each with an
`interface_type`, a non-empty `reason` that existing interfaces cannot fit, and
`parts` containing named scalar fields. The narrowly scoped v0.1.0 generator
supports scalar fields needed by the test binding. It emits `.msg`, `.srv`, or
`.action` definitions and an interface package's CMake/package metadata under
`build/agents/<agent-id>/interfaces/<package>/`. Field declaration order is
preserved. Every generated type must be used by a non-existing endpoint; an
existing endpoint never requests a generated wrapper. Compiling or installing
these packages is separate from manifest generation.
