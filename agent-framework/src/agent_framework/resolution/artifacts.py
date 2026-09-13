"""Write only deterministic M2 model/lock artifacts beneath the workspace build tree."""

import os
import tempfile
from pathlib import Path

from agent_framework.serialization.json import canonical_json, normalize

from .errors import ResolutionError
from .resolver import Resolution


def write_artifacts(resolution: Resolution, workspace: Path) -> tuple[Path, Path]:
    identifier = resolution.agent.id
    if (
        not identifier
        or identifier in (".", "..")
        or any(char in identifier for char in ("/", "\\", "\x00"))
    ):
        raise ResolutionError("unsafe Agent artifact directory name")
    root = workspace.resolve()
    directory = root / "build" / "agents" / identifier
    if not directory.resolve().is_relative_to(root / "build"):
        raise ResolutionError("artifact directory escapes workspace build tree")
    model = normalize(resolution.agent)
    assert isinstance(model, dict)
    payloads = (
        canonical_json({"schema_version": "0.1.0", **model}),
        canonical_json(resolution.binding_lock),
    )
    paths = (directory / "resolved_agent_model.json", directory / "binding_lock.json")
    directory.mkdir(parents=True, exist_ok=True)
    for path, payload in zip(paths, payloads, strict=True):
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return paths
