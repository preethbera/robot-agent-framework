"""Backward-compatible facade for modular code generation."""

from . import GenerationError, generate_python
from .emitter import load_artifacts, render
from .schema_types import Types, identifier, schema_from_data, unique_names

__all__ = [
    "GenerationError",
    "Types",
    "generate_python",
    "identifier",
    "load_artifacts",
    "render",
    "schema_from_data",
    "unique_names",
]
