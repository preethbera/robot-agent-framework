# M3: ROS2 Realization Builder

## Goal

Translate the Resolved Agent Model plus binding ROS2 descriptions into one deterministic ROS2 Realization Manifest.

## Implement

- ROS2 endpoint description model,
- topic/service/action support,
- QoS description and validation,
- Channel-to-ROS mapping,
- endpoint name templates,
- optional allowed Agent Definition ROS2 overrides,
- existing-interface reuse,
- custom interface artifact generation only when a test case requires it,
- `project/build/agents/<agent-id>/ros2_realization.json`.

## Tests

Use the external test binding from M2.

Cover:

- direct Property topic mapping,
- request/response service mapping,
- sensing Capability output stream mapping,
- one multi-endpoint Capability,
- rejected invalid override,
- deterministic manifest generation.

## Acceptance

The framework can fully describe the ROS2 realization without generating the Python API yet.

## Implementation references

- [ROS2 design and approved v0.1.0 override contract](../design/ROS2%20Realization.md)
- [M3 progress and acceptance record](../progress/M3_PROGRESS.md)
