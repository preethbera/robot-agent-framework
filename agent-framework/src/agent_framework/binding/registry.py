"""Registry of installed definitions and their distribution provenance."""

from collections.abc import Mapping
from dataclasses import dataclass

from .definition import BindingDefinition
from .errors import MissingBindingError


@dataclass(frozen=True, slots=True, kw_only=True)
class PackageRecord:
    distribution: str
    version: str
    binding_api_version: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BindingRegistry:
    definitions: Mapping[str, BindingDefinition]
    packages: Mapping[str, PackageRecord]

    def get(self, identifier: str) -> BindingDefinition:
        try:
            return self.definitions[identifier]
        except KeyError as error:
            raise MissingBindingError(f"missing binding definition {identifier!r}") from error
