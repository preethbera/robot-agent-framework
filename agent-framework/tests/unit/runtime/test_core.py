from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pytest
from agent_framework.runtime.agent import (
    AgentRuntime,
    AgentSpec,
    BindingSpec,
    ChannelSpec,
    Component,
)
from agent_framework.runtime.channel import Buffer
from agent_framework.runtime.errors import AgentError, FailureCode
from agent_framework.runtime.registry import Registry


class Services:
    def __init__(self, fail: str = "") -> None:
        self.registry: Registry[AgentRuntime] = Registry()
        self.events: list[str] = []
        self.fail = fail

    def create_component(self, agent: AgentRuntime, binding: BindingSpec) -> Component:
        events = self.events
        fail = self.fail

        @dataclass
        class TestComponent:
            def start(self) -> None:
                events.append(f"start:{binding.id}")
                if binding.id == fail:
                    raise RuntimeError("startup failure")

            def close(self) -> None:
                events.append(f"close:{binding.id}")

        return TestComponent()

    def close(self) -> None:
        self.events.append("services:close")


def spec() -> AgentSpec:
    return AgentSpec(
        "test",
        (ChannelSpec("sensor.output", "sensor", "agent_to_consumer", "output"),),
        (),
        tuple(BindingSpec(name, {}, (), {}) for name in ("first", "second")),
        (),
    )


def test_bounded_queue_and_latest_cache() -> None:
    queue = Buffer[int](2)
    queue.put(1)
    queue.put(2)
    assert queue.read(0) == 1
    queue.put(3)
    queue.put(4)
    with pytest.raises(AgentError) as failure:
        queue.read(0)
    assert failure.value.code == FailureCode.OVERFLOW
    cache = Buffer[int](latest=True)
    for value in range(100):
        cache.put(value)
    assert cache.read(0) == cache.read(0) == 99


def test_close_wakes_blocked_reader() -> None:
    queue = Buffer[int]()
    with ThreadPoolExecutor() as executor:
        waiting = executor.submit(queue.read, 5)
        queue.close()
        with pytest.raises(AgentError) as failure:
            waiting.result(timeout=1)
    assert failure.value.code == FailureCode.CLOSED


def test_timeout_is_structured() -> None:
    with pytest.raises(AgentError) as failure:
        Buffer[int]().read(0)
    assert failure.value.code == FailureCode.TIMEOUT


def test_components_start_before_ready_and_close_in_reverse_order() -> None:
    services = Services()
    agent = AgentRuntime(spec(), instance_id="one", runtime=services)
    assert agent.ready and services.events == ["start:first", "start:second"]
    agent.close()
    agent.close()
    assert services.events == ["start:first", "start:second", "close:second", "close:first"]
    assert services.registry.values() == ()


def test_partial_startup_failure_unwinds_components() -> None:
    services = Services(fail="second")
    with pytest.raises(AgentError) as failure:
        AgentRuntime(spec(), instance_id="one", runtime=services)
    assert failure.value.code == FailureCode.STARTUP
    assert services.events == ["start:first", "start:second", "close:second", "close:first"]
    assert services.registry.values() == ()


def test_late_results_do_not_enter_a_new_operation() -> None:
    agent = AgentRuntime(spec(), instance_id="one", runtime=Services())
    first = agent.begin("sensor")
    with pytest.raises(AgentError, match="active operation"):
        agent.begin("sensor")
    first.close()
    second = agent.begin("sensor")
    agent.emit("sensor.output", 1, first)
    with pytest.raises(AgentError) as failure:
        second.read("sensor.output", 0)
    assert failure.value.code == FailureCode.TIMEOUT
    agent.emit("sensor.output", 2, second)
    assert second.read("sensor.output", 0) == 2
    agent.close()


def test_duplicate_instance_does_not_unregister_live_agent() -> None:
    services = Services()
    agent = AgentRuntime(spec(), instance_id="one", runtime=services)
    with pytest.raises(AgentError) as failure:
        AgentRuntime(spec(), instance_id="one", runtime=services)
    assert failure.value.code == FailureCode.BUSY
    assert services.registry.values() == (agent,)
    agent.close()
