# Binding Model

## 1. Purpose

A Binding connects generic Agent semantics to one concrete technology integration.

Bindings are independently installable packages and may be developed independently of the framework. During Prototype v0 development, first-party/local binding source lives under `project/bindings/<binding>/` so the coding agent can see the complete system context. The framework must still treat them as installed packages, not as source-tree submodules.

## 2. Binding Responsibilities

Each binding definition declares:

1. the Property or Capability it can realize,
2. default generic semantics,
3. mandatory requirements,
4. supported configuration,
5. ROS2 realization description,
6. executable runtime logic when required,
7. dependencies on other binding definitions when required.

A binding package may publish many modular binding definitions.

Example identifiers:

```text
px4.position
px4.velocity
px4.arm
px4.offboard.position
lidar.scan
lidar.stream
```

## 3. Binding API Version

Every binding package declares compatible Binding API versions.

Framework package version, binding package version, and Binding API version are separate.

Incompatible bindings are rejected during resolution before runtime.

## 4. Binding Definition

Every Binding Definition must expose the following information, regardless of the internal Python class layout:

```text
id
description
primitive: property | capability
default semantic model
mandatory requirements
configuration schema
dependencies
ROS2 realization template
runtime mode
runtime factory optional
```

## 5. Direct Binding

Use a direct binding when existing ROS2 endpoints plus static mapping/conversion are sufficient.

Example: an Agent position Property backed directly by an existing state topic with a deterministic field/frame conversion.

## 6. Code-backed Binding

Use a code-backed binding when realization requires logic such as:

- sequencing,
- state machines,
- multiple ROS2 endpoints,
- heartbeat/liveness generation,
- mode transitions,
- derived computation,
- runtime-dependent conversion,
- lifecycle handling.

Example: PX4 Offboard position control.

## 7. Sensor Bindings

Sensor functionality is modeled through Capabilities.

Examples:

```text
lidar.scan
    Capability invocation
    -> result point cloud
```

```text
lidar.stream
    Capability session
    -> output point-cloud stream
```

Sensor health, temperature, current configuration, or other information that characterizes the Agent/component may separately be exposed as Properties.

## 8. Responsibility Ownership

Bindings may support configurable ownership for requirements.

Example:

```text
liveness_owner: binding | application
```

If the binding owns a requirement, its internal communication may remain hidden from the Python API. If the application owns it, the requirement must appear in the Resolved Agent Model and later generated API.
