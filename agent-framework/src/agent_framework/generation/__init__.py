"""Modular static typed Python API generator from build artifacts."""

from __future__ import annotations

import ast
import os
import tempfile
from pathlib import Path

from .emitter import load_artifacts, render
from .schema_types import GenerationError, identifier


def generate_python(directory: Path) -> Path:
    """Generate typed Python API module from resolved model and ROS2 realization artifacts."""
    model, manifest = load_artifacts(directory)
    try:
        source = render(model, manifest)
        ast.parse(source)
    except (KeyError, TypeError, SyntaxError) as error:
        raise GenerationError(f"cannot generate Python API: {error}") from error
    package = directory / "python" / ("agent_" + identifier(model["id"]))
    if not package.resolve().is_relative_to(directory.resolve()):
        raise GenerationError("Python output path escapes Agent build directory")
    package.mkdir(parents=True, exist_ok=True)
    for name, content in (("__init__.py", source), ("py.typed", "")):
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=package, mode="w", encoding="utf-8", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(content)
            os.replace(temporary, package / name)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return package


__all__ = ["GenerationError", "generate_python", "load_artifacts", "render"]
