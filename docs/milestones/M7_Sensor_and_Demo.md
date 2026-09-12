# M7: Independent Sensor Capability and Supervisor Demo

## Goal

Prove that independent sensing technologies compose with the Agent without becoming part of the PX4 binding and without introducing a third primitive.

## Implement

- one independent LiDAR or equivalent sensor binding distribution under `project/bindings/<sensor>/`,
- sensor acquisition represented as a Capability,
- a continuous high-bandwidth output Channel,
- sensor health/status Property when supported,
- mixed Group containing sensor Property/Properties and sensing Capability/Capabilities,
- performance instrumentation for latency, queue depth, and dropped samples,
- final prototype Agent Definition under `project/agents/` and Deployment Specification under `project/deployments/`.

## Supervisor Demo

Show:

1. Docker environment starts reproducibly.
2. One Agent Definition selects external bindings without repeating their ROS2 details.
3. Binding packages are discovered externally.
4. Resolution produces `project/build/agents/<agent-id>/resolved_agent_model.json`.
5. ROS2 realization produces `project/build/agents/<agent-id>/ros2_realization.json`.
6. Python API is generated only after ROS2 realization.
7. PX4 state/control works through the generated API.
8. Independent sensor Capability streams data through the same Agent API.
9. A Group mixes sensor Properties and Capabilities.
10. Multiple Agent instances can run without framework-core changes.
11. Application source contains no direct ROS2 or PX4 APIs.
