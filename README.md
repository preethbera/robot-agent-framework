# Project Workspace

Version: **0.1.0**

This directory is the canonical coding workspace. Open **this `project/` directory** in Codex, Antigravity, VS Code, or another coding platform.

Do not open only `agent-framework/` as if it were the complete system. The framework, local binding packages, Agent Definitions, deployments, generated artifacts, Docker environment, system tests, and architecture documents are peer parts of this workspace.

## Scope and layout

M0 supplies packaging, the documented framework module skeleton, Docker, and
development checks. M1 implements the technology-independent core model and
explicit build-time validation. M2 adds installed bindings, safe Agent Definition
loading, resolution, and deterministic artifacts. ROS2 realization starts in M3.
The authoritative plan starts at [docs/README.md](docs/README.md).

| Directory | Purpose |
| --- | --- |
| `agent-framework/` | One installable distribution, import package `agent_framework` |
| `bindings/` | Independent binding distributions, introduced in later milestones |
| `agents/` | Reusable Agent Definitions |
| `deployments/` | Runtime instance configuration |
| `build/` | Ignored generated artifacts, never source code |
| `tests/integration/`, `tests/e2e/` | Cross-package and system tests |
| `docker/` | Canonical development environment |
| `docs/` | Authoritative architecture, design, and milestone documents |

The framework version is defined only in `agent-framework/pyproject.toml` package
metadata. At runtime, read `importlib.metadata.version("agent-framework")`.

## Windows, WSL2, and Docker Desktop

1. Install or enable WSL2 and a Linux distribution. In PowerShell, `wsl --list
   --verbose` should show version `2` for your distribution.
2. Start Docker Desktop in Linux container mode, enable **Use the WSL 2 based
   engine**, and enable your distribution under **Settings > Resources > WSL
   Integration**. See the [official Docker WSL guide](https://docs.docker.com/desktop/features/wsl/).
3. Keep this complete workspace in the WSL Linux filesystem, for example
   `~/work/project`, and open that directory through your editor's WSL support.
   Run the commands below in a WSL terminal at `project/`.
4. Confirm `docker version` reports both a client and a server, and `docker
   compose version` succeeds. Docker requires network access for the first build.

```bash
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
docker compose -f docker/compose.yaml build dev
docker compose -f docker/compose.yaml run --rm dev
```

You can also build from `project/docker/` with `docker compose build dev`.
Compose resolves its build context and mount relative to `compose.yaml`, so both
forms mount the complete workspace at `/workspace/project`.

The container uses ROS2 Jazzy on Ubuntu 24.04, Python 3.12, and an editable framework
installation. The shell starts with the container's ROS environment sourced.
Source edits are immediately visible; rebuild after changing package metadata,
the Dockerfile, or dependency pins. UID/GID build arguments keep files created on
the workspace mount owned by the WSL user. The container's Python environment is
writable by that user for installing future independent local bindings.

There is one workspace bind mount. No host ROS2, PX4, Gazebo, Python environment,
or Docker socket is mounted, and no host ROS environment variables are forwarded.
PX4 and Gazebo are deferred until a milestone requires them.

## Validate M0–M2

Run model tests, packaging regressions, and static checks in a fresh development container:

```bash
docker compose -f docker/compose.yaml run --rm -T dev bash docker/check.sh
```

This verifies Ubuntu/Jazzy, imports the image-provided `rclpy`, checks the workspace
mount, then runs pytest, Ruff lint/format checks, and strict mypy. Packaging tests
check the uninstalled import boundary, metadata, wheel contents, and installation
and imports in a fresh environment without ROS or other runtime dependencies.

The individual commands, run inside the container from `/workspace/project`, are:

```bash
python -m pytest -c agent-framework/pyproject.toml agent-framework/tests bindings/test/tests tests
python -m ruff check --config agent-framework/pyproject.toml .
python -m ruff format --check --config agent-framework/pyproject.toml .
python -m mypy --config-file agent-framework/pyproject.toml agent-framework/src/agent_framework agent-framework/tests bindings/test/src bindings/test/tests tests
```

M1 tests cover mixed/nested Groups and cycle rejection, multi-Channel Capabilities,
sensing sessions and invocations, contract-static Properties, Constraint targets,
Channel correlation, and schema/constant validation. Cross-package integration
and e2e directories are reserved for later milestones. There is no runtime
communication hot path to benchmark in M1.

## Reproducibility

The Dockerfile pins the official ROS Jazzy/Noble multi-platform image by SHA-256
digest. Additional Ubuntu packages come from the `20260912T000000Z`
[Ubuntu snapshot](https://snapshot.ubuntu.com/). Python development tools and
their transitive dependencies are pinned with wheel hashes in
`docker/requirements-dev.txt` for Python 3.12 on Linux amd64/arm64. The build backend
is pinned in package metadata as well. M0 adds no framework runtime dependencies.

Refresh environment pins deliberately and rerun all M0 checks; refreshing
development dependencies does not change the project's `0.1.0` version.
No `PYTHONPATH` source injection is needed or supported as an installation method.
Docker remains the acceptance environment even if checks also pass on a local
Python installation.

## Resolve the M2 example

Inside the development container, from `/workspace/project`:

```bash
python - <<'PYTHON'
from pathlib import Path
from agent_framework.definition.loader import load_agent_definition
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.resolution.artifacts import write_artifacts

result = resolve_agent(load_agent_definition(Path("agents/test_agent/agent.yaml")))
for path in write_artifacts(result, Path.cwd()):
    print(path)
PYTHON
```

This writes only `resolved_agent_model.json` and `binding_lock.json` beneath
`build/agents/test_agent/`. The test binding is installed independently in the
image. Discovery uses package entry points, including for local editable installs.
M2 retains ROS2 overrides/templates for the next stage without materializing ROS2.

Outside Docker, install `agent-framework[build]` to enable YAML loading; core
model imports and installed binding discovery do not require the YAML dependency.
The loader accepts one YAML 1.2 document with the documented keys, rejects duplicate
keys and executable tags, and limits input to 1 MiB, nesting to 64 levels, and
expanded data to 100,000 nodes. See the [safe-loader API](https://yaml.dev/doc/ruamel.yaml/api/).

M2 checkpoint/resume status is in [docs/progress/M2_PROGRESS.md](docs/progress/M2_PROGRESS.md).
