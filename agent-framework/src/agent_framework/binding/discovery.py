"""Discover referenced installed entry points without inspecting workspace paths."""

from collections.abc import Iterable
from importlib.metadata import entry_points

from .api import BINDING_API_VERSION, ENTRY_POINT_GROUP, BindingPackage
from .definition import BindingDefinition, validate_binding
from .errors import BindingError, IncompatibleBindingError, MissingBindingError
from .registry import BindingRegistry, PackageRecord


def discover_bindings(references: Iterable[str]) -> BindingRegistry:
    """Load only requested namespaces and transitive declared dependencies once."""
    available = entry_points(group=ENTRY_POINT_GROUP)
    definitions: dict[str, BindingDefinition] = {}
    packages: dict[str, PackageRecord] = {}
    pending = list(references)
    visited: set[str] = set()
    while pending:
        reference = pending.pop()
        if reference in visited:
            continue
        visited.add(reference)
        namespace, separator, _ = reference.partition(".")
        if not namespace or not separator:
            raise MissingBindingError(f"binding reference must be qualified: {reference!r}")
        if namespace not in packages:
            candidates = [point for point in available if point.name == namespace]
            if not candidates:
                raise MissingBindingError(f"missing installed binding package {namespace!r}")
            if len(candidates) != 1:
                raise BindingError(f"ambiguous installed binding namespace {namespace!r}")
            point = candidates[0]
            try:
                provider = point.load()
                package = provider()
            except Exception as error:
                raise BindingError(
                    f"cannot load binding provider {namespace!r}: {error}"
                ) from error
            if not isinstance(package, BindingPackage):
                raise BindingError(f"{namespace}: provider must return BindingPackage")
            if BINDING_API_VERSION not in package.api_versions:
                raise IncompatibleBindingError(
                    f"{namespace}: incompatible Binding API {package.api_versions}; "
                    f"requires {BINDING_API_VERSION}"
                )
            if point.dist is None:
                raise BindingError(f"{namespace}: entry point has no distribution provenance")
            packages[namespace] = PackageRecord(
                distribution=point.dist.metadata["Name"],
                version=point.dist.version,
                binding_api_version=BINDING_API_VERSION,
            )
            for definition in package.definitions:
                validate_binding(definition)
                if not definition.id.startswith(namespace + ".") or definition.id in definitions:
                    raise BindingError(f"invalid or duplicate binding ID {definition.id!r}")
                definitions[definition.id] = definition
        if reference not in definitions:
            raise MissingBindingError(f"missing binding definition {reference!r}")
        pending.extend(definitions[reference].dependencies)
    return BindingRegistry(definitions=definitions, packages=packages)
