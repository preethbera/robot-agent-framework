"""PX4 binding catalog; importing/discovering it requires no PX4 or ROS installation."""

from agent_framework.binding.api import BindingPackage

__version__ = "0.1.0"


def get_bindings() -> BindingPackage:
    from . import commands, offboard, properties

    return BindingPackage(
        api_versions=("0.1.0",),
        definitions=properties.definitions() + commands.definitions() + (offboard.definition(),),
    )
