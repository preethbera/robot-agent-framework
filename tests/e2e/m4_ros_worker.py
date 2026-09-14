"""ROS-aware test peer and harness; kept outside the application source."""

import importlib
import sys
import time
from pathlib import Path
from threading import Event
from typing import Any
from unittest.mock import patch

from agent_framework.ros2.runtime import Runtime
from agent_framework.runtime.errors import AgentError, FailureCode


def direct() -> None:
    Command = importlib.import_module("agent_binding_test_interfaces.srv").Command
    ReentrantCallbackGroup = importlib.import_module("rclpy.callback_groups").ReentrantCallbackGroup
    Float64 = importlib.import_module("std_msgs.msg").Float64

    shared = Runtime()
    node = shared._ros.create_node("m4_native_peer", context=shared.context)
    shared.executor.add_node(node)
    group = ReentrantCallbackGroup()
    liveness = Event()

    def command(request: Any, response: Any) -> Any:
        if request.value == 13.0:
            time.sleep(0.3)
        response.result = request.value * 2
        return response

    def publish(temperature: Any, sensor: Any, value: float) -> None:
        temperature.publish(Float64(data=value))
        sensor.publish(Float64(data=7.0))

    for instance, value in (("m4_a", 21.5), ("m4_b", 31.5)):
        temperature = node.create_publisher(Float64, f"/native/{instance}/temperature", 5)
        sensor = node.create_publisher(Float64, f"/native/{instance}/sensor/output", 5)
        node.create_timer(
            0.2,
            lambda t=temperature, s=sensor, v=value: publish(t, s, v),
            callback_group=group,
        )
        node.create_service(Command, f"/native/{instance}/command", command, callback_group=group)
        node.create_subscription(
            Float64,
            f"/native/{instance}/sensor/liveness",
            lambda message: liveness.set(),
            5,
        )
    try:
        application = importlib.import_module("m4_application")
        with (
            patch(
                "agent_framework.definition.loader.parse_agent_definition",
                side_effect=AssertionError("runtime YAML parsing"),
            ),
            patch(
                "agent_framework.binding.discovery.discover_bindings",
                side_effect=AssertionError("runtime discovery"),
            ),
            patch(
                "agent_framework.resolution.resolver.resolve_agent",
                side_effect=AssertionError("runtime resolution"),
            ),
            patch(
                "agent_framework.generation.python.generate_python",
                side_effect=AssertionError("runtime generation"),
            ),
            patch(
                "agent_framework.model.schema.validate_schema",
                side_effect=AssertionError("runtime schema resolution"),
            ),
        ):
            application.run()
        assert liveness.wait(2), "application liveness did not reach native endpoint"
    finally:
        shared.executor.remove_node(node)
        node.destroy_node()
        shared.close()


def factories() -> None:
    from agent_binding_test import runtime as fixture

    module = importlib.import_module("agent_codebacked_agent")
    with Runtime() as shared:
        with module.Agent(instance_id="factory", runtime=shared) as agent:
            assert agent.temperature.get(timeout=5) == 23.0
            assert agent.command.invoke(42.0) == 42.0
            with agent.lidar_stream.start() as session:
                assert session.output.read(timeout=5) == 4.0
        assert shared.executor.get_nodes() == []
        assert fixture.EVENTS[-3:] == [
            ("close", "temperature"),
            ("close", "lidar_stream"),
            ("close", "command"),
        ]
        fixture.EVENTS.clear()
        fixture.FAIL_START = "lidar_stream"
        try:
            module.Agent(instance_id="startup_failure", runtime=shared)
        except AgentError as error:
            assert error.code == FailureCode.STARTUP
        else:
            raise AssertionError("startup failure ignored")
        assert fixture.EVENTS[-3:] == [
            ("close", "temperature"),
            ("close", "lidar_stream"),
            ("close", "command"),
        ]
        assert shared.executor.get_nodes() == [] and shared.registry.values() == ()
        fixture.FAIL_START = ""
        fixture.FAIL_CREATE = "lidar_stream"
        try:
            module.Agent(instance_id="creation_failure", runtime=shared)
        except AgentError as error:
            assert error.code == FailureCode.STARTUP
        else:
            raise AssertionError("factory failure ignored")
        assert shared.executor.get_nodes() == [] and shared.registry.values() == ()
        fixture.FAIL_CREATE = ""


def protocols() -> None:
    Command = importlib.import_module("agent_binding_test_interfaces.srv").Command
    Fibonacci = importlib.import_module("example_interfaces.action").Fibonacci
    actions = importlib.import_module("rclpy.action")
    groups = importlib.import_module("rclpy.callback_groups")

    def wait(future: Any) -> Any:
        ready = Event()
        future.add_done_callback(lambda done: ready.set())
        assert ready.wait(5), "ROS future did not complete"
        return future.result()

    shared = Runtime()
    node = shared._ros.create_node("m4_protocol_peer", context=shared.context)
    shared.executor.add_node(node)
    group = groups.ReentrantCallbackGroup()

    def execute(handle: Any) -> Any:
        handle.publish_feedback(Fibonacci.Feedback(sequence=[0, 1]))
        if handle.request.order == 99:
            end = time.monotonic() + 5
            while not handle.is_cancel_requested and time.monotonic() < end:
                time.sleep(0.01)
            assert handle.is_cancel_requested
            handle.canceled()
        else:
            time.sleep(0.05)
            handle.succeed()
        return Fibonacci.Result(sequence=[0, 1, 1, 2])

    server = actions.ActionServer(
        node,
        Fibonacci,
        "/native/action_client/fibonacci",
        execute_callback=execute,
        callback_group=group,
        cancel_callback=lambda handle: actions.CancelResponse.ACCEPT,
    )
    client = actions.ActionClient(
        node, Fibonacci, "/native/action_server/fibonacci", callback_group=group
    )
    service = node.create_client(Command, "/native/service_server/command", callback_group=group)
    try:
        module = importlib.import_module("agent_action_agent")
        with module.Agent(instance_id="action_client") as agent:
            with agent.task.start() as call:
                call.goal.send(4)
                assert call.feedback.read(timeout=5) == [0, 1]
                assert call.result.read(timeout=5) == [0, 1, 1, 2]
            with agent.task.start() as call:
                call.goal.send(99)
                assert call.feedback.read(timeout=5) == [0, 1]
                call.cancel.send(module.Payload_task_cancel())
                try:
                    call.result.read(timeout=5)
                except AgentError as error:
                    assert error.code == FailureCode.CANCELLED
                else:
                    raise AssertionError("native cancellation did not reach the API")
        module = importlib.import_module("agent_command_server_agent")
        with (
            module.Agent(instance_id="service_server") as agent,
            agent.command.start() as call,
        ):
            assert service.wait_for_service(timeout_sec=5)
            response = service.call_async(Command.Request(value=5.0))
            assert call.request.read(timeout=5) == 5.0
            call.result.send(10.0)
            assert wait(response).result == 10.0
        module = importlib.import_module("agent_action_server_agent")
        with (
            module.Agent(instance_id="action_server") as agent,
            agent.task.start() as call,
        ):
            assert client.wait_for_server(timeout_sec=5)
            handle = wait(client.send_goal_async(Fibonacci.Goal(order=3)))
            assert handle.accepted and call.goal.read(timeout=5) == 3
            response = handle.get_result_async()
            call.feedback.send([0, 1])
            call.result.send([0, 1, 1])
            result = wait(response)
            assert result.status == 4 and list(result.result.sequence) == [0, 1, 1]
    finally:
        client.destroy()
        server.destroy()
        shared.executor.remove_node(node)
        node.destroy_node()
        shared.close()


if __name__ == "__main__":
    for directory in sys.argv[2:]:
        sys.path.insert(0, str(Path(directory)))
    if sys.argv[1] == "direct":
        direct()
    elif sys.argv[1] == "factories":
        factories()
    else:
        protocols()
