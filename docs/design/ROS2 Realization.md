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
