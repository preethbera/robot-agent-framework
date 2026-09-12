# Environment and Repository

## 1. Workspace Rule

All development happens inside one top-level workspace named **`project/`**. This is the directory that should be opened in Codex, Antigravity, VS Code, or another coding environment.

The workspace gives the coding agent simultaneous context for:

- the generic framework,
- first-party and locally developed binding packages,
- Agent Definitions,
- Deployment Specifications,
- generated build artifacts,
- cross-component tests,
- architecture, design, and milestone documents.

`project/` is a workspace boundary, not an installable Python package.

## 2. Canonical Workspace Layout

```text
project/
├── README.md
├── .gitignore
│
├── docker/
│   ├── Dockerfile
│   ├── compose.yaml
│   └── entrypoint.sh
│
├── docs/
│   ├── README.md
│   ├── CODING_AGENT_PROMPT.md
│   ├── Implementation Specification.md
│   ├── architecture/
│   │   ├── Agent Definition Model.md
│   │   └── System Architecture and Design Decisions.md
│   ├── design/
│   │   ├── Environment and Repository.md
│   │   ├── Core Model.md
│   │   ├── Agent Definition and Resolution.md
│   │   ├── Binding Model.md
│   │   ├── ROS2 Realization.md
│   │   └── Python API Runtime and Deployment.md
│   └── milestones/
│       ├── M0_Bootstrap.md
│       ├── M1_Core_Model.md
│       ├── M2_Binding_and_Resolution.md
│       ├── M3_ROS2_Realization.md
│       ├── M4_Python_API_and_Runtime.md
│       ├── M5_PX4_Binding.md
│       ├── M6_Multi_Agent.md
│       └── M7_Sensor_and_Demo.md
│
├── agent-framework/
│   ├── pyproject.toml
│   ├── README.md
│   ├── src/
│   │   └── agent_framework/
│   │       └── ...
│   └── tests/
│       └── ...
│
├── bindings/
│   ├── README.md
│   ├── test/
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── agent_binding_test/
│   │   └── tests/
│   ├── px4/
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── agent_binding_px4/
│   │   └── tests/
│   └── <future-binding>/
│       └── ...
│
├── agents/
│   ├── README.md
│   └── <agent-id>/
│       └── agent.yaml
│
├── deployments/
│   ├── README.md
│   └── <deployment-id>.yaml
│
├── build/
│   └── agents/
│       └── <agent-id>/
│           ├── resolved_agent_model.json
│           ├── binding_lock.json
│           ├── ros2_realization.json
│           ├── interfaces/
│           └── python/
│
└── tests/
    ├── integration/
    └── e2e/
```

### 2.1 Naming rule

Use **`agent-framework/`** for the repository/workspace directory and **`agent_framework`** for the importable Python package.

Likewise, a binding may live at `bindings/px4/`, have distribution name `agent-binding-px4`, and expose import package `agent_binding_px4`.

This keeps filesystem grouping concise while preserving normal Python package naming.

### 2.2 Workspace versus distributable packages

The initial project may be maintained as one workspace or monorepo so the coding agent has full context. This does **not** make bindings part of the framework package.

Each directory under `bindings/` is its own independently installable Python distribution with its own `pyproject.toml`, source package, tests, and version. A binding can later move to a separate repository or be published independently without changing the framework architecture.

The framework must never import a binding by hardcoded source path. Local bindings are installed into the development environment like normal packages, typically as editable installs during development, and discovered through the Binding API mechanism.

## 3. Host Environment

Primary development host:

```text
Windows laptop
    -> WSL2
    -> Docker Desktop with WSL2 backend
```

ROS2 Jazzy, Gazebo, PX4 SITL, and related tools are already installed in WSL2, but the project must **not** rely on those host installations for reproducibility.

Docker is the canonical development and integration environment so the entire `project/` workspace can be moved to another compatible machine with minimal environment drift.

## 4. Container Strategy

The Docker configuration is owned by the **workspace root**, not by `agent-framework`, because one environment must develop and test the framework, local bindings, Agent Definitions, generated artifacts, and integration tests together.

Use a ROS2 Jazzy / Ubuntu 24.04 compatible base image. Add only dependencies required by active milestones.

The containerized environment must eventually support:

- Python framework development,
- ROS2 Jazzy,
- Gazebo required by the prototype,
- PX4 SITL required by integration milestones,
- local binding package development,
- Agent Definition build/generation commands,
- tests and static analysis.

Do not split conceptual components into multiple containers unless there is a concrete isolation or deployment requirement. Extra containers create network and operational boundaries that are not justified by architecture diagrams alone.

The development container should mount the whole `project/` workspace and use it as the working context.

## 5. Framework Repository

`project/agent-framework/` contains **one installable Python distribution** whose import package is `agent_framework`. The directories inside `src/agent_framework/` are internal subpackages of that one package.

The layout below is the planned Prototype v0.1.0 structure and is authoritative. Files may be introduced when their milestone becomes active, but responsibilities must remain separated as shown.

```text
project/agent-framework/
├── pyproject.toml
├── README.md
│
├── src/
│   └── agent_framework/
│       ├── __init__.py
│       │
│       ├── model/
│       │   ├── __init__.py
│       │   ├── agent.py
│       │   ├── property.py
│       │   ├── capability.py
│       │   ├── channel.py
│       │   ├── constraint.py
│       │   ├── group.py
│       │   └── schema.py
│       │
│       ├── definition/
│       │   ├── __init__.py
│       │   ├── model.py
│       │   ├── loader.py
│       │   ├── validation.py
│       │   └── errors.py
│       │
│       ├── binding/
│       │   ├── __init__.py
│       │   ├── api.py
│       │   ├── definition.py
│       │   ├── discovery.py
│       │   ├── registry.py
│       │   └── errors.py
│       │
│       ├── resolution/
│       │   ├── __init__.py
│       │   ├── resolver.py
│       │   ├── merge.py
│       │   ├── validation.py
│       │   ├── artifacts.py
│       │   └── errors.py
│       │
│       ├── ros2/
│       │   ├── __init__.py
│       │   ├── model.py
│       │   ├── builder.py
│       │   ├── endpoints.py
│       │   ├── qos.py
│       │   ├── mapping.py
│       │   ├── introspection.py
│       │   ├── interfaces.py
│       │   ├── manifest.py
│       │   ├── runtime.py
│       │   └── errors.py
│       │
│       ├── generation/
│       │   ├── __init__.py
│       │   ├── python.py
│       │   └── templates/
│       │
│       ├── runtime/
│       │   ├── __init__.py
│       │   ├── agent.py
│       │   ├── property.py
│       │   ├── capability.py
│       │   ├── channel.py
│       │   ├── invocation.py
│       │   ├── session.py
│       │   ├── registry.py
│       │   └── errors.py
│       │
│       ├── deployment/
│       │   ├── __init__.py
│       │   ├── model.py
│       │   ├── loader.py
│       │   ├── instances.py
│       │   ├── registry.py
│       │   └── errors.py
│       │
│       ├── serialization/
│       │   ├── __init__.py
│       │   ├── json.py
│       │   └── hashing.py
│       │
│       └── cli/
│           ├── __init__.py
│           └── main.py
│
└── tests/
    ├── unit/
    │   ├── model/
    │   ├── definition/
    │   ├── binding/
    │   ├── resolution/
    │   ├── ros2/
    │   ├── generation/
    │   ├── runtime/
    │   └── deployment/
    ├── integration/
    └── fixtures/
```

### 5.1 Internal subpackage responsibilities

| Subpackage | Responsibility | Must not contain |
|---|---|---|
| `model` | Technology-independent Agent semantic types | ROS2, PX4, YAML parsing |
| `definition` | Agent Definition structure, loading, structural validation | Technology-specific binding implementation |
| `binding` | Binding API, definitions, discovery, registry | PX4 or vendor-specific implementations |
| `resolution` | Merge Agent Definition with selected bindings and produce the Resolved Agent Model | ROS2 endpoint construction |
| `ros2` | Build and execute ROS2 realization from binding-provided mappings | PX4-specific semantics not supplied by bindings |
| `generation` | Generate the Python-facing API after ROS2 realization is complete | Agent Definition parsing or binding discovery |
| `runtime` | Generic generated-API runtime abstractions such as invocation/session handling | Development-time resolution |
| `deployment` | Agent Instance and multi-agent deployment configuration | Agent semantic definitions |
| `serialization` | Deterministic JSON serialization and hashing | Domain logic |
| `cli` | Thin command entry points | Core logic belonging to other subpackages |

### 5.2 Why `src/` exists

There is still only one import package, `agent_framework`. `src/` is the repository source-layout directory. It keeps packaging/import behavior explicit and prevents accidental reliance on the repository root as an import location.

### 5.3 No `contract/` package

There is no separate Agent Contract artifact. The fixed linear flow is:

```text
Agent Definition
    -> Resolved Agent Model
    -> ROS2 Realization
    -> Python API Generation
```

Serialization belongs to the stage that owns each artifact and the shared `serialization/` utilities.

## 6. Binding Packages

First-party and locally developed bindings live under `project/bindings/` during development.

Example PX4 binding:

```text
project/bindings/px4/
├── pyproject.toml
├── README.md
├── src/
│   └── agent_binding_px4/
│       ├── __init__.py
│       └── ...
└── tests/
```

The exact internal PX4 binding layout is defined when the PX4 milestone is implemented. Do not place PX4 code inside `agent-framework`.

A third-party installed binding does not need its source code under `project/bindings/`; it only needs to be installed in the environment and discoverable through the Binding API. The workspace contains source for bindings being developed as part of this project.

## 7. Agent Definitions and Deployments

Reusable Agent Definitions live under:

```text
project/agents/<agent-id>/agent.yaml
```

Runtime instance configuration lives under:

```text
project/deployments/<deployment-id>.yaml
```

The deployment file references built Agent Definitions. It must not duplicate Agent semantics.

## 8. Generated Build Artifacts

Generated artifacts are not source files and live under `project/build/`, normally gitignored.

For each Agent Definition:

```text
project/build/agents/<agent-id>/
├── resolved_agent_model.json
├── binding_lock.json
├── ros2_realization.json
├── interfaces/
└── python/
```

`interfaces/` is populated only if custom ROS2 interfaces are actually required. `python/` contains the generated Python-facing API/package for that Agent Definition.

Build output must never be written into a binding source package or into `src/agent_framework/`.

## 9. Test Boundaries

- Unit tests for `agent_framework` live in `project/agent-framework/tests/`.
- Unit tests for a binding live inside that binding directory.
- Cross-package integration tests live in `project/tests/integration/`.
- Full Docker/ROS2/PX4/simulator workflows live in `project/tests/e2e/` when introduced.

This separation keeps package-level tests independently runnable while giving the workspace a place for system tests.

## 10. Libraries and Dependency Rules

### Runtime/core

Prefer Python standard library features where sufficient:

- `dataclasses`,
- `enum`,
- `typing`,
- `importlib.metadata`,
- `json`,
- `hashlib`,
- `pathlib`.

ROS2 runtime code uses `rclpy` and required standard ROS2 packages.

### Build-time configuration

Use `ruamel.yaml` in safe mode for YAML 1.2 parsing with duplicate-key rejection. YAML parsing occurs at development/build time, never in the per-message hot path.

### Explicitly prohibited

- Pydantic,
- arbitrary `eval`/`exec`,
- executable YAML tags,
- heavy dependency-injection frameworks,
- a general third-party plugin framework when Python entry points are sufficient.

### Development

- `pytest`,
- `ruff`,
- `mypy`.

Do not add dependencies preemptively. Add a library only when an active milestone has a concrete requirement.

## 11. Binding Discovery in the Workspace

External bindings register through Python package entry points.

Local workspace bindings must use the exact same discovery mechanism as independently installed bindings. During development they may be installed in editable mode inside the container, but the framework must not discover them by scanning `project/bindings/` directly or importing files by path.

This ensures that moving a binding to another repository or installing it from a package index does not change framework behavior.

Discovery occurs during resolution/build, not for every runtime message. Incompatible Binding API versions are rejected before runtime.
