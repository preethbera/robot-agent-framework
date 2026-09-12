# M4: Python API Generation and ROS2 Runtime

## Goal

Generate and run the Python-facing Agent API from the completed semantic and ROS2 artifacts.

## Inputs

- `project/build/agents/<agent-id>/resolved_agent_model.json`
- `project/build/agents/<agent-id>/ros2_realization.json`

## Implement

- Python API generator writing to `project/build/agents/<agent-id>/python/`,
- generated typed Property access,
- invocation Capability access,
- session Capability access,
- Capability output/feedback/result handling,
- shared ROS2 context/executor,
- runtime endpoint construction from the manifest, including direct use of existing endpoints,
- optional binding runtime factory support for code-backed bindings,
- bounded caches/queues where required,
- timeouts and structured runtime errors.

## Acceptance

- Test application imports no `rclpy` or ROS-specific message classes.
- Test Property works through the generated API.
- Test invocation Capability works through the generated API.
- Test sensing Capability produces a stream through the generated API.
- No Agent Definition parsing occurs in the per-message path.
