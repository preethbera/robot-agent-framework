from agent_framework.binding.api import BindingPackage

__version__ = "0.1.0"


def get_bindings() -> BindingPackage:
    from . import capabilities, properties

    return BindingPackage(
        api_versions=("0.1.0",),
        definitions=properties.definitions() + capabilities.definitions(),
    )
