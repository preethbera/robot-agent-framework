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

### v0.1.0 code-backed binding factory contract

A code-backed factory is an internal runtime extension point, loaded only from
its finalized manifest reference. It receives binding instance identity,
already-resolved configuration, the relevant finalized ROS2 realization, Agent
instance/runtime identity and namespace, and access to framework-owned shared
ROS2 services. It must not parse Agent YAML, discover plugins, resolve schemas
or bindings, or generate code at runtime.

The factory returns a component implementing the framework lifecycle protocol.
The component provides/registers its binding's Channel implementations. Internal
Python protocol names are implementation details; technology-specific types
must not appear in the generated application-facing API.

The framework creates shared ROS2 infrastructure first, then components, and
starts components before declaring the Agent instance ready. Partial startup
failure shuts down started components in reverse order and releases resources
from incomplete creation. Normal shutdown stops components before destroying
shared infrastructure. Repeated lifecycle calls should be safe where practical.

The framework owns shared context/executor and shared infrastructure. Components
own their own subscriptions, publishers, timers, background work, state, and
technology resources, releasing them during shutdown. Factories retain no
independent long-lived resources after returning a component. No middleware hop,
dependency-injection framework, runtime discovery, or runtime schema resolution
is introduced.

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
        arm:
          target_system: 1

  - id: uav_02
    agent: inspection_uav
    config:
      ros_namespace: /uav_02
      bindings:
        arm:
          target_system: 2
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

### Deployment implementation contract

Instance parameters use the separate declaration described in `Binding Model.md`.
Binding targets are resolved exposure aliases, not package names. The example
above assumes an `arm` exposure. Configure each command exposure that requires a
different native target; the framework does not infer PX4 grouping or semantics.

Deployment loads generated packages from explicit build paths without changing
`sys.path` or retaining private entries in `sys.modules`. Applications importing
generated types can supply `agent_types={"definition_id": GeneratedAgent}` to
Deployment, preserving nominal payload class identity. Private loading is useful
for supervisors that only inspect Properties; generated payloads must come from
the same generated module as their Agent constructor.

All instances share one runtime. Cleanup visits instances in reverse creation
order, including partial startup failure, before destroying owned infrastructure.

Generated output Channels expose read-only `statistics` snapshots: current queue
depth, dropped sample count, and last-read queue residence latency in seconds.
Latency is unavailable until a read. This is runtime delivery instrumentation,
not sensor acquisition latency or network/DDS loss accounting. Overflow preserves
M4's explicit terminal failure and bounded storage behavior.
