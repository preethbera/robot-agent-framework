# Python API, Runtime, and Deployment

## 1. Python API Generation

The Python API is generated **after** ROS2 realization.

Inputs:

```text
project/build/agents/<agent-id>/resolved_agent_model.json
project/build/agents/<agent-id>/ros2_realization.json
```

The semantic model tells the generator what each Property/Capability means. The ROS2 manifest tells it exactly how communication is realized. Generated Python output is written under `project/build/agents/<agent-id>/python/`.

## 2. Application Boundary

Application source must not import:

```text
rclpy
px4_msgs
sensor-driver ROS message classes
binding implementation modules
ROS2 QoS classes
```

Application code interacts only with generated Agent-facing types and APIs.

## 3. Generated Surface

The exact Python syntax is allowed to evolve during implementation, but it must provide typed access to:

- Properties,
- invocation Capabilities,
- session Capabilities,
- Capability input/output/feedback/result Channels,
- relevant Constraints and metadata when applications need them.

Do not expose a generic dictionary-only API as the final design if static generation can provide stronger typing.

## 4. Runtime

Runtime responsibilities include:

- shared ROS2 context/executor,
- creation of endpoints from the realization manifest,
- direct connection to existing ROS2 endpoints when possible,
- adapters and conversions only when required,
- code-backed binding runtime instances only when required,
- bounded caches where required,
- timeouts and structured failure states,
- Agent Instance registration.

No YAML parsing, binding discovery, schema resolution, or code generation occurs per message.

## 5. Deployment Specification

Agent semantics are not repeated for each runtime instance.

A Deployment Specification creates instances from already built Agent Definitions.

Conceptual example:

```yaml
schema_version: "0.1.0"
instances:
  - id: uav_01
    agent: inspection_uav
    config:
      ros_namespace: /uav_01
      bindings:
        px4:
          instance: 1

  - id: uav_02
    agent: inspection_uav
    config:
      ros_namespace: /uav_02
      bindings:
        px4:
          instance: 2
```

Binding-specific instance keys are validated by their binding packages. Generic deployment code must not hardcode PX4 fields.

## 6. Multi-Agent Runtime

The runtime maintains a registry keyed by Agent Instance ID.

It must support:

- many instances of one Agent Definition,
- heterogeneous Agent Definitions in the same process/runtime,
- isolated instance state,
- shared ROS2 infrastructure where safe.

Avoid global singleton Agent objects.

## 7. Future Deployment Independence

Prototype v0 keeps ROS2 on the application machine/runtime environment.

Future deployment independence may insert a remote transport boundary beneath the generated Agent API. Preserve this possibility, but do not implement gRPC or another remote protocol in Prototype v0 unless explicitly requested later.
