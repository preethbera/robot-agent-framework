"""ArduPilot binding catalog; importing/discovering it requires no ArduPilot or ROS installation."""

from agent_framework.binding.api import BindingPackage

__version__ = "0.1.0"


def get_bindings() -> BindingPackage:
    from . import commands, guided, properties

    return BindingPackage(
        api_versions=("0.1.0",),
        definitions=properties.definitions() + commands.definitions() + (guided.definition(),),
    )

