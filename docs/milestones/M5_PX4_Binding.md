# M5: PX4 Binding Package

## Goal

Implement the real independently installable PX4 binding distribution under `project/bindings/px4/` (distribution name `agent-binding-px4`) against the pinned PX4/ROS2 versions.

## Minimum Scope

Properties:

- position,
- velocity,
- armed state,
- flight mode.

Capabilities:

- arm,
- disarm,
- land,
- hold,
- orbit,
- Offboard position-control session.

## Requirements

- Reuse PX4 ROS2 interfaces.
- Keep PX4 types out of the generated public Agent API.
- Keep command acknowledgement separate from observable state Properties.
- Offboard session supports binding-owned and application-owned liveness where the binding declares both valid.
- Binding owns PX4 endpoints, message types, QoS defaults, mode transitions, acknowledgements, and sequencing.
- Use code-backed binding only where required.

## Acceptance

A Python application controls PX4 SITL through the generated Agent API with no direct ROS2/PX4 imports.
