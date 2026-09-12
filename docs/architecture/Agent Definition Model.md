---
title: Agent Definition Model
version: 0.1.0
status: implementation baseline
updated: 2026-09-13
---

# Agent Definition Model

> [!abstract] Scope
> This document defines the semantic model used by an Agent Definition and its resolved form. ROS2 endpoint details, binding implementation, Python API generation, deployment, and runtime mechanics are defined elsewhere.

## 1. Purpose

The Agent Definition Model describes the functionality intentionally exposed by a robotic Agent without hardcoding a robot type, control stack, sensor vendor, or planning method.

A concrete Agent Definition is informed by the real hardware and software stack and by the bindings available for that stack. The model itself remains general.

## 2. Core Concepts

| Concept | Kind | Purpose |
|---|---|---|
| **Agent** | Structural | Root description of one reusable Agent definition |
| **Property** | Primitive | Information that characterizes the Agent or one of its components |
| **Capability** | Primitive | A function or behavior the Agent performs |
| **Channel** | Supporting | One unidirectional logical communication flow |
| **Constraint** | Supporting | A machine-readable condition or valid-use limit |
| **Group** | Structural | Organizes related Properties, Capabilities, and subgroups |

There are exactly two primitives in Prototype v0: **Property** and **Capability**.

## 3. Property

A **Property** represents information about the Agent itself or one of its components.

Examples include:

- position and velocity,
- armed state and current mode,
- battery state,
- motor or joint state,
- sensor health and sensor temperature,
- dimensions, mass, or other static Agent characteristics when applications need them,
- derived values that describe the Agent itself.

A Property may be dynamic or contract-static.

A Property does **not** represent environmental measurements merely because the Agent can communicate them. LiDAR point clouds, camera images, radar returns, scans, and similar sensed environment data are outputs of sensing Capabilities.

A writable Property is permitted only when changing the value is semantically a state/configuration update rather than requesting an operation. If the interaction asks the Agent to perform a function, use a Capability.

## 4. Capability

A **Capability** represents a function, behavior, or operation performed by the Agent.

Capabilities include both actuation and sensing.

Examples:

- arm, disarm, land, hold, orbit,
- external position control,
- open or close a gripper,
- deploy a mechanism,
- perform one LiDAR scan,
- stream LiDAR scans,
- capture an image,
- stream camera frames,
- run a perception or sensing function.

Prototype v0 uses two execution forms:

- **invocation**: a discrete operation that eventually completes,
- **session**: a function that remains active until stopped, terminated, or otherwise ended.

A sensing Capability may have no recurring consumer input and may primarily produce an output stream. For example, a LiDAR streaming Capability can be a session whose main Channel is an Agent-to-consumer stream.

Whether a session is explicitly started by the application or automatically activated by deployment/runtime configuration is a realization policy, not a new primitive.

## 5. Classification Rule

Use these rules in order:

1. If it describes the Agent or one of its components, model it as a Property.
2. If it represents a function the Agent performs, including sensing or perception, model it as a Capability.

The physical device itself is not automatically a primitive. A LiDAR subsystem may expose:

```text
Group: lidar
    Property: health
    Property: temperature
    Capability: scan
    Capability: stream_scans
```

## 6. Channel

A **Channel** represents one unidirectional logical flow associated with a Property or Capability.

A Channel is technology-neutral. It does not itself mean a ROS2 topic, service, action, PX4 message, socket, or other transport object.

Prototype v0 Channel semantics must express:

- direction,
- payload schema,
- single occurrence or stream,
- lifetime,
- purpose,
- optional correlation to another Channel,
- timing requirements when relevant,
- delivery requirements when relevant.

### 6.1 Direction

```text
consumer_to_agent
agent_to_consumer
```

### 6.2 Cardinality

```text
single
stream
```

### 6.3 Lifetime

```text
persistent
invocation
session
```

### 6.4 Purpose

```text
value
input
output
acknowledgement
feedback
result
cancellation
liveness
status
```

`output` is used for Capability-produced information that is not naturally a final result or progress feedback, such as a continuous sensor stream.

### 6.5 Examples

Property:

```text
position value <-
```

Invocation Capability:

```text
request ->
        <- acknowledgement
        <- result
```

Long-running Capability:

```text
goal ->
     <- feedback stream
     <- result
cancel ->
```

Sensing session:

```text
start/session control -> optional
sensor output stream  <-
status stream         <- optional
```

A command acknowledgement is not the same as an independently observable Property. For example, a successful arm acknowledgement is distinct from `armed_state`.

## 7. Constraint

A **Constraint** represents a machine-readable condition or limit required for valid use of the Agent or one of its exposed elements.

Constraints may target:

- Agent,
- Group,
- Property,
- Capability,
- Channel,
- payload field.

Examples include:

- maximum translational or angular speed,
- acceleration limits,
- steering and joint limits,
- payload limits,
- valid command ranges,
- preconditions,
- mutual exclusion,
- supported values,
- consumer-owned timing requirements.

Prefer correct schemas and capability design over redundant negative constraints. A ground rover movement Capability should normally accept the dimensions it can actually use rather than accept arbitrary 3D motion and add a `cannot fly` constraint.

The absence of a Capability is also meaningful. If the Agent has no flight Capability, an application must not assume it can fly.

## 8. Group

A **Group** is organizational only.

A Group may contain any mixture of:

- Properties,
- Capabilities,
- nested Groups.

This supports subsystem-oriented organization such as `mobility`, `lidar`, `camera`, or `manipulator` without forcing Properties and Capabilities into separate trees.

Group membership does not imply sequencing, exclusivity, timing, or runtime behavior.

## 9. Agent

An **Agent** is the root of one reusable Agent Definition.

It contains the Properties, Capabilities, Channels, Constraints, and Groups intentionally exposed by that definition.

Runtime identity is separate. The same Agent Definition may be instantiated multiple times, and different Agent Definitions may coexist in one deployment.

## 10. Technology Boundary

Technology-specific requirements may affect the semantic definition when the application must satisfy them, but the technology-specific mechanism remains in the binding/realization layer.

Example:

```text
Agent-visible requirement:
    liveness update within a maximum gap

Binding/ROS2 realization:
    PX4 OffboardControlMode endpoint, QoS, timer, and sequencing
```

If the binding owns the liveness requirement internally, it does not need to appear as an application-facing Channel. If the application owns it, it must appear in the resolved Agent Model and generated API.

## 11. Design Rules

- Exactly two primitives exist: Property and Capability.
- Property is about the Agent itself or its components.
- Sensing and perception are Capabilities.
- Environmental sensor data is Capability output, feedback, or result data.
- One Capability may require many Channels.
- Groups may mix Properties and Capabilities.
- Constraints express valid-use limitations, not technology implementation details.
- Technology-specific mechanisms belong in bindings and ROS2 realization.
- No fixed list of robot capabilities is hardcoded into the model.
