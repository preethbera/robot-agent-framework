from agent_binding_test import get_bindings
from agent_framework.binding.definition import configure_binding, validate_binding
from agent_framework.model import Capability, Execution, Property, Purpose


def test_declared_elements() -> None:
    package = get_bindings()
    assert package.api_versions == ("0.1.0",)
    for definition in package.definitions:
        validate_binding(definition)
    assert isinstance(package.definitions[0].default_semantics.element, Property)
    invocation = package.definitions[1].default_semantics.element
    assert (
        isinstance(invocation, Capability)
        and invocation.execution is Execution.INVOCATION
    )
    stream = configure_binding(
        package.definitions[2], {"liveness_owner": "application"}
    )
    assert {channel.purpose for channel in stream.channels} == {
        Purpose.OUTPUT,
        Purpose.LIVENESS,
    }
    assert stream.responsibility_ownership == {"liveness": "application"}
