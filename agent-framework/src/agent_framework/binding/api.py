"""External Binding API 0.1.0; discovery and configuration are build-time only."""

from dataclasses import dataclass

from .definition import BindingDefinition

BINDING_API_VERSION = "0.1.0"
ENTRY_POINT_GROUP = "agent_framework.bindings"


@dataclass(frozen=True, slots=True, kw_only=True)
class BindingPackage:
    """Returned by a zero-argument entry-point provider.

    Entry-point name is the first component of qualified binding IDs. Explicit
    supported versions avoid silently treating pre-1.0 APIs as compatible.
    """

    api_versions: tuple[str, ...]
    definitions: tuple[BindingDefinition, ...]
