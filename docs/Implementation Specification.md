---
title: Prototype v0 Implementation Specification
version: 0.1.0
status: implementation baseline
updated: 2026-09-13
---

# Prototype v0 Implementation Specification

> [!important]
> This document is the short implementation entry point. The coding workspace root is `project/`. Detailed architecture, design, and milestone documents belong under `project/docs/`.

## 1. Workspace

```text
project/
├── agent-framework/   # generic framework distribution
├── bindings/          # independently installable local binding distributions
├── agents/            # reusable Agent Definitions
├── deployments/       # runtime Agent Instance configuration
├── build/             # generated artifacts, normally gitignored
├── tests/             # cross-package integration/e2e tests
├── docker/            # canonical development environment
└── docs/              # architecture/design/milestone instructions
```

Open the complete `project/` folder in the coding platform.

## 2. Required Architecture

```text
Actual Stack + Installed Bindings
            +
      Agent Definition
            ↓
         Resolver
            ↓
  Resolved Agent Model
            ↓
 ROS2 Realization Builder
            ↓
 ROS2 Realization Manifest
            ↓
  Python API Generator
            ↓
 Generated Python Agent API
```

Runtime uses the shortest valid path. Direct bindings may connect the framework ROS2 runtime directly to existing ROS2 endpoints. Code-backed binding runtime components are inserted only when executable integration logic is required.

## 3. Model

Exactly two primitives exist:

- **Property**: information about the Agent itself or one of its components.
- **Capability**: a function performed by the Agent, including sensing and perception.

Sensor data is delivered through Capability output/result/feedback Channels. Do not introduce a third sensor-data primitive.

Supporting concepts:

- Channel
- Constraint

Structural concepts:

- Agent
- Group

Groups may mix Properties and Capabilities.

## 4. Developer Input

The developer writes one Agent Definition that:

- selects bindings,
- chooses exposed functionality,
- configures supported binding options,
- assigns Agent-facing names,
- defines Groups and Constraints,
- optionally overrides allowed ROS2 realization details.

Binding-provided endpoint names, message types, QoS defaults, mandatory requirements, and technology sequencing are not repeated.

## 5. Build Artifacts

For Agent `<agent-id>`, write generated artifacts under:

```text
project/build/agents/<agent-id>/
```

Artifacts include:

1. `resolved_agent_model.json`
2. `binding_lock.json`
3. `ros2_realization.json`
4. generated Python Agent API/package under `python/`
5. custom ROS2 interface artifacts under `interfaces/` only when required

## 6. Runtime and Performance Rules

- No Pydantic.
- No YAML parsing, binding discovery, schema resolution, code generation, or generic reflection in per-message paths.
- Reuse existing ROS2 interfaces when correct.
- Avoid unnecessary republishing, serialization, and copies.
- Code-backed binding runtime components are optional, not mandatory hops.
- Use bounded queues/caches.
- Make timeouts and failures explicit.
- Measure high-bandwidth paths.

## 7. Environment

Canonical development environment:

```text
Windows + WSL2 + Docker Desktop
    ↓
project/docker/
    ↓
containerized ROS2 Jazzy / Ubuntu 24.04 development environment
```

The container mounts the complete `project/` workspace and must not depend on host ROS2, Gazebo, or PX4 installations.

## 8. Implementation Order

Use the milestone documents. Do not implement the entire project in one pass.
