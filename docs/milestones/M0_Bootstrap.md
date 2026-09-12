# M0: Workspace, Environment, and Repository Bootstrap

## Goal

Create the top-level **`project/` workspace**, the reproducible Docker development environment, and the explicit `agent-framework` package skeleton. Do not implement semantic behavior yet.

## Tasks

1. Create/open `project/` as the workspace root.
2. Place the architecture, design, milestone, implementation, and coding-agent documents under `project/docs/` using the structure in `project/docs/design/Environment and Repository.md`.
3. Create workspace-level `README.md`, `.gitignore`, and `docker/` files.
4. Create `project/agent-framework/` using the exact internal package boundaries defined in `project/docs/design/Environment and Repository.md`.
5. Create `project/bindings/`, `project/agents/`, `project/deployments/`, `project/build/`, and `project/tests/` workspace directories.
6. Do not place technology-specific binding implementation code inside `agent-framework`.
7. Add a Docker development environment for ROS2 Jazzy on Ubuntu 24.04. Docker configuration belongs at `project/docker/`.
8. Mount the entire `project/` workspace into the development container.
9. Add Python development tooling, pytest, Ruff, and mypy.
10. Set framework version to `0.1.0` with one package metadata source.
11. Document the Windows + WSL2 + Docker Desktop workflow.
12. Verify the container does not rely on host ROS2/PX4/Gazebo installations.

## Workspace Boundary

The coding environment must be opened at `project/`, not only at `project/agent-framework/`. Future binding packages, Agent Definitions, Deployment Specifications, generated artifacts, and cross-component tests are peer parts of the same development workspace.

`project/` itself is not an importable Python package.

## Framework Boundary

`project/agent-framework/` contains one independently installable distribution whose import package is `agent_framework`. Its internal subpackages include `model`, `definition`, `binding`, `resolution`, `ros2`, `generation`, `runtime`, `deployment`, `serialization`, and `cli`.

Do not replace this explicit structure with generic placeholder directories.

## Acceptance

- The top-level directory is `project/` and is suitable to open directly in Codex/Antigravity/VS Code.
- A fresh compatible host with WSL2 and Docker Desktop can build the development image from `project/docker/`.
- The development container mounts and can access the complete workspace.
- `agent_framework` imports only after package installation.
- The planned framework internal subpackage skeleton matches `project/docs/design/Environment and Repository.md`.
- Workspace directories for bindings, agents, deployments, build artifacts, and system tests exist.
- pytest, Ruff, and mypy commands run successfully in the container.
- No technology-specific binding code exists inside `agent-framework`.
