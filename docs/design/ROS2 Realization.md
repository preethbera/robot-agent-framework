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
