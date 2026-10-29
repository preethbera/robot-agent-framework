"""PX4 native binding package."""

from agent_framework.binding.api import BindingPackage

__version__ = "0.1.0"


def get_bindings() -> BindingPackage:
    from . import commands, offboard, properties

    return BindingPackage(
        api_versions=("0.1.0",),
        definitions=properties.definitions() + commands.definitions() + offboard.definitions(),
        environment_provider="agent_binding_px4.environment:PX4EnvironmentProvider",
    )


__all__ = ["__version__", "get_bindings"]
