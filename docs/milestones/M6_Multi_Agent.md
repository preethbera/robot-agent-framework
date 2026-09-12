# M6: Multi-Agent Deployment

## Goal

Support multiple instances of one Agent Definition and heterogeneous definitions in one runtime.

## Implement

- Deployment Specification loader for files under `project/deployments/`,
- AgentInstance,
- per-instance binding configuration,
- namespace/endpoint template expansion,
- runtime registry keyed by instance ID,
- shared ROS2 runtime infrastructure,
- isolated per-instance state.

## Required Demo

Run at least two instances of the same Agent Definition with distinct runtime identities and ROS2 mappings.

Add one minimal second Agent Definition under `project/agents/` or use a test binding to prove heterogeneous coexistence.
