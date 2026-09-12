# Core Model

## 1. Model Types

Implement these concepts:

```text
Agent
Property
Capability
Channel
Constraint
Group
PayloadSchema
```

Use typed slotted dataclasses and enums where appropriate. Keep semantic model types independent of ROS2 classes.

## 2. Property

Required fields:

```text
id
description
schema
channels
constant_value optional
metadata optional
```

Rules:

- Property describes the Agent or one of its components.
- Dynamic Properties use one or more Channels.
- Contract-static Properties may use `constant_value` and no runtime Channel.
- Agent state, telemetry about the Agent, configuration state, component health, and static Agent characteristics are valid Properties.
- Environmental sensor measurements are not Properties.
- A consumer-to-Agent Property Channel is valid only if setting the value is semantically a state/configuration update rather than requesting a function.

## 3. Capability

Required fields:

```text
id
description
execution: invocation | session
channels
metadata optional
```

A Capability may represent actuation, sensing, perception, computation, or another Agent-performed function.

Examples of sensor modeling:

```text
Capability: lidar_scan
    execution: invocation
    result: point cloud
```

```text
Capability: lidar_stream
    execution: session
    output: point-cloud stream
```

No third sensor primitive is introduced.

## 4. Channel

Required fields:

```text
id
direction
schema
cardinality
lifetime
purpose
correlates_with optional
timing optional
delivery optional
```

Enums:

```text
direction:
    consumer_to_agent
    agent_to_consumer

cardinality:
    single
    stream

lifetime:
    persistent
    invocation
    session

purpose:
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

Timing fields when needed:

```text
min_rate_hz
max_rate_hz
max_gap_s
max_latency_s
max_age_s
```

Delivery semantics when needed:

```text
reliability: reliable | best_effort
ordering: ordered | unordered
```

These are semantic requirements, not ROS2 QoS objects.

## 5. PayloadSchema

Prototype v0 schema kinds:

```text
scalar
record
array
sequence
enum
opaque
```

Scalar types:

```text
bool
int8 int16 int32 int64
uint8 uint16 uint32 uint64
float32 float64
string
bytes
```

Semantic metadata may include:

```text
unit
frame
meaning
bounds
description
```

Use `opaque` only when a structured generic representation would impose unacceptable copying or destroy an efficient representation. The public application API must still not expose a ROS2 message class directly.

## 6. Constraint

Do not create a general expression language in Prototype v0.

Required fields:

```text
id
description
target
kind
parameters
consumer_visible
```

Targets may reference:

```text
agent
group
property
capability
channel
payload field
```

Initial kinds:

```text
range
allowed_values
precondition
mutual_exclusion
```

Channel timing and delivery requirements remain on Channel rather than being duplicated as Constraints.

## 7. Group

Required fields:

```text
id
description
members
subgroups
```

`members` may reference any mixture of Property and Capability IDs.

Groups may nest. Reject cycles during resolution.

Group membership has no behavior by itself.

## 8. Agent

Required fields:

```text
id
description
properties
capabilities
channels
constraints
groups
metadata
```

This model represents the resolved reusable Agent semantics, not one runtime instance.
