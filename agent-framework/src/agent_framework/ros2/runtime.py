"""ROS2 Jazzy transport; imports and entity setup occur once, outside message paths."""

from __future__ import annotations

import copy
import re
from collections.abc import Callable, Mapping
from importlib import import_module
from threading import Event, RLock, Thread
from time import monotonic
from typing import Any, Self, cast

from agent_framework.runtime.agent import (
    AgentRuntime,
    BindingSpec,
    Codec,
    Component,
    FactoryContext,
    Operation,
)
from agent_framework.runtime.errors import AgentError, FailureCode
from agent_framework.runtime.registry import Registry


def reference(value: str) -> Any:
    module, separator, member = value.partition(":")
    if (
        not separator
        or not member.isidentifier()
        or any(not part.isidentifier() for part in module.split("."))
    ):
        raise AgentError(FailureCode.STARTUP, "Invalid explicit runtime reference", target=value)
    return getattr(import_module(module), member)


def endpoint_name(endpoint: Mapping[str, Any], instance_id: str, namespace: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", instance_id):
        raise AgentError(FailureCode.INVALID_VALUE, "ROS2 instance ID must be a name token")
    namespace = namespace.strip("/")
    if namespace and any(
        not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token) for token in namespace.split("/")
    ):
        raise AgentError(FailureCode.INVALID_VALUE, "Invalid ROS2 namespace")
    if "name" in endpoint:
        return str(endpoint["name"])
    name = str(endpoint["name_template"]).format(instance_id=instance_id, namespace=namespace)
    # A root/empty namespace substitution must not leave a double slash.
    return re.sub(r"/+", "/", name)


def adapt_codec(codec: Codec, adapter: Callable[[Any], Any]) -> Codec:
    def encode(message: Any, value: Any) -> None:
        codec.encode(message, adapter(value))

    def decode(message: Any) -> Any:
        return adapter(codec.decode(message))

    return Codec(codec.channel, codec.endpoint, codec.part, encode, decode)


class Runtime:
    """Own shared ROS2 infrastructure and an instance-local registry."""

    def __init__(self) -> None:
        self.registry: Registry[AgentRuntime] = Registry()
        self.lock = RLock()
        self.stopping = Event()
        self.closed = False
        self._ros = import_module("rclpy")
        self.context = import_module("rclpy.context").Context()
        self._ros.init(context=self.context)
        try:
            self.executor = import_module("rclpy.executors").MultiThreadedExecutor(
                num_threads=2, context=self.context
            )
            self.thread = Thread(target=self._spin, name="agent-ros2-executor", daemon=True)
            self.thread.start()
        except Exception:
            self.context.try_shutdown()
            raise

    def _spin(self) -> None:
        while not self.stopping.is_set():
            try:
                self.executor.spin_once(timeout_sec=0.05)
            except AgentError:
                # Entity callbacks already reported the error to their owning operation.
                continue
            except Exception as error:
                if self.stopping.is_set():
                    return
                # Removing a scope can invalidate an entity already selected by the executor.
                if type(error).__name__ == "InvalidHandle":
                    continue
                for agent in self.registry.values():
                    agent.fail(
                        AgentError(FailureCode.TRANSPORT, str(error), target=agent.instance_id)
                    )
                return

    def create_component(self, agent: AgentRuntime, binding: BindingSpec) -> Component:
        with self.lock:
            if self.closed:
                raise AgentError(FailureCode.CLOSED, "Shared ROS2 runtime is closed")
            scope = Scope(self, agent, binding)
            try:
                if binding.runtime_factory is None:
                    return DirectComponent(scope)
                allowed = {item.id for item in agent.spec.channels if item.owner == binding.id}

                def register(channel: str, send: Callable[[object, Operation], None]) -> None:
                    if channel not in allowed:
                        raise AgentError(
                            FailureCode.STARTUP,
                            "Factory registered another binding's Channel",
                            target=channel,
                        )
                    agent.register(channel, send)

                def emit(channel: str, value: object, operation: Operation | None = None) -> None:
                    if channel not in allowed:
                        raise AgentError(
                            FailureCode.TRANSPORT,
                            "Factory emitted another binding's Channel",
                            target=channel,
                        )
                    agent.emit(channel, value, operation)

                context = FactoryContext(
                    binding.id,
                    copy.deepcopy(binding.configuration),
                    copy.deepcopy(binding.realization),
                    agent.instance_id,
                    agent.spec.id,
                    agent.namespace,
                    scope,
                    register,
                    emit,
                )
                component = reference(binding.runtime_factory)(context)
                if not callable(getattr(component, "start", None)) or not callable(
                    getattr(component, "close", None)
                ):
                    raise AgentError(
                        FailureCode.STARTUP, "Factory must return a start/close component"
                    )
                return ManagedComponent(cast(Component, component), scope)
            except Exception:
                scope.close()
                raise

    def close(self) -> None:
        with self.lock:
            if self.closed:
                return
            self.closed = True
        errors = []
        for agent in reversed(self.registry.values()):
            try:
                agent.close()
            except Exception as error:
                errors.append(error)
        self.stopping.set()
        self.executor.wake()
        self.thread.join(timeout=5.0)
        try:
            if not self.executor.shutdown(timeout_sec=5.0):
                errors.append(RuntimeError("executor shutdown timed out"))
        finally:
            self.context.try_shutdown()
        if self.thread.is_alive() or errors:
            raise AgentError(FailureCode.TRANSPORT, "Shared runtime cleanup failed") from (
                errors[0] if errors else None
            )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class Scope:
    """Component resources use shared services; a private node bounds fallback cleanup."""

    def __init__(self, runtime: Runtime, agent: AgentRuntime, binding: BindingSpec) -> None:
        self.runtime = runtime
        self.agent = agent
        self.binding = binding
        self._node: Any = None
        self._cleanup: list[Callable[[], Any]] = []
        self.closed = False
        self.group = import_module("rclpy.callback_groups").ReentrantCallbackGroup()

    @property
    def node(self) -> Any:
        if self.closed:
            raise AgentError(FailureCode.CLOSED, "Component scope is closed")
        if self._node is None:
            name = "agent_" + re.sub(
                r"[^A-Za-z0-9_]", "_", self.agent.instance_id + "_" + self.binding.id
            )
            self._node = self.runtime._ros.create_node(
                name, namespace=self.agent.namespace or "/", context=self.runtime.context
            )
            self.runtime.executor.add_node(self._node)
        return self._node

    def own(self, cleanup: Callable[[], Any]) -> None:
        """Track cleanup of component resources not already owned by its ROS node."""
        self._cleanup.append(cleanup)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        errors = []
        for cleanup in reversed(self._cleanup):
            try:
                cleanup()
            except Exception as error:
                errors.append(error)
        self._cleanup.clear()
        if self._node is not None:
            self.runtime.executor.remove_node(self._node)
            self._node.destroy_node()
            self._node = None
        if errors:
            raise AgentError(
                FailureCode.TRANSPORT, "Component resource cleanup failed"
            ) from errors[0]


class ManagedComponent:
    def __init__(self, component: Component, scope: Scope) -> None:
        self.component = component
        self.scope = scope
        self.started = False
        self.closed = False

    def start(self) -> None:
        if not self.started and not self.closed:
            self.component.start()
            self.started = True

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.component.close()
        finally:
            self.scope.close()


class DirectComponent:
    def __init__(self, scope: Scope) -> None:
        self.scope = scope
        self.agent = scope.agent
        self.started = False
        self.closed = False
        self._codecs: dict[str, tuple[Codec, ...]] = {}

    def qos(self, values: Mapping[str, Any] | None, baseline: str) -> Any:
        module = import_module("rclpy.qos")
        profile = copy.copy(getattr(module, baseline))
        for name, value in (values or {}).items():
            if name != "depth":
                enum = getattr(
                    module,
                    {
                        "history": "HistoryPolicy",
                        "reliability": "ReliabilityPolicy",
                        "durability": "DurabilityPolicy",
                    }[name],
                )
                value = enum[value.upper()]
            setattr(profile, name, value)
        return profile

    def start(self) -> None:
        if self.started or self.closed:
            return
        for endpoint in self.scope.binding.realization["endpoints"]:
            identifier = endpoint["id"]
            codecs = []
            for codec in self.agent.spec.codecs:
                if codec.endpoint != identifier:
                    continue
                if codec.adapter:
                    adapter = reference(codec.adapter)
                    codec = adapt_codec(codec, adapter)
                codecs.append(codec)
            self._codecs[identifier] = tuple(codecs)
            package, kind, name = endpoint["interface_type"].split("/")
            interface = getattr(import_module(f"{package}.{kind}"), name)
            native = endpoint_name(endpoint, self.agent.instance_id, self.agent.namespace)
            role = endpoint["role"]
            qos = self.qos(
                endpoint.get("qos"),
                "qos_profile_default" if kind == "msg" else "qos_profile_services_default",
            )
            if role == "publisher":
                publisher = self.scope.node.create_publisher(interface, native, qos)
                self._publisher(identifier, interface, publisher)
            elif role == "subscriber":
                self._subscription(identifier, interface, native, qos)
            elif role == "client":
                client = self.scope.node.create_client(
                    interface, native, qos_profile=qos, callback_group=self.scope.group
                )
                self._client(identifier, interface, client)
            elif role == "action_client":
                self._action_client(endpoint, interface, native)
            elif role in {"server", "action_server"}:
                self._server(endpoint, interface, native, qos)
            else:
                raise AgentError(
                    FailureCode.STARTUP, "Unsupported finalized endpoint role", target=identifier
                )
        self.started = True

    def _receive(
        self, identifier: str, part: str, message: Any, operation: Operation | None = None
    ) -> None:
        try:
            for codec in self._codecs[identifier]:
                if codec.part == part:
                    self.agent.emit(codec.channel, codec.decode(message), operation)
        except Exception as error:
            failure = AgentError(FailureCode.TRANSPORT, str(error), target=identifier)
            if operation is None:
                self.agent.fail(failure)
            else:
                operation.fail(failure)

    def _parts(self, identifier: str, part: str) -> tuple[Codec, ...]:
        return tuple(codec for codec in self._codecs[identifier] if codec.part == part)

    def _owner(self, identifier: str) -> str:
        owners = {
            self.agent.channel_specs[codec.channel].owner for codec in self._codecs[identifier]
        }
        if len(owners) != 1:
            raise AgentError(FailureCode.STARTUP, "Endpoint must belong to one binding instance")
        return owners.pop()

    def _subscription(self, identifier: str, interface: Any, name: str, qos: Any) -> None:
        codecs = self._codecs[identifier]
        if all(self.agent.channel_specs[codec.channel].property for codec in codecs):
            self.scope.node.create_subscription(
                interface,
                name,
                lambda message: self._receive(identifier, "message", message),
                qos,
                callback_group=self.scope.group,
            )
        else:

            def open_subscription(operation: Operation) -> None:
                subscription = self.scope.node.create_subscription(
                    interface,
                    name,
                    lambda message: self._receive(identifier, "message", message, operation),
                    qos,
                    callback_group=self.scope.group,
                )
                operation.cleanup.append(lambda: self.scope.node.destroy_subscription(subscription))

            self.agent.openers.setdefault(self._owner(identifier), []).append(open_subscription)

    def _publisher(self, identifier: str, interface: Any, publisher: Any) -> None:
        for codec in self._parts(identifier, "message"):

            def send(value: object, operation: Operation, selected: Codec = codec) -> None:
                message = self._assemble(
                    identifier, "message", interface, selected, value, operation
                )
                if message is not None:
                    publisher.publish(message)

            self.agent.register(codec.channel, send)

    def _assemble(
        self,
        identifier: str,
        part: str,
        interface: Any,
        codec: Codec,
        value: object,
        operation: Operation,
    ) -> Any:
        state = operation.transport.setdefault(identifier, {})
        message, seen = state.setdefault(part, (interface(), set()))
        codec.encode(message, value)
        seen.add(codec.channel)
        if seen == {item.channel for item in self._parts(identifier, part)}:
            del state[part]
            return message
        return None

    def _client(self, identifier: str, interface: Any, client: Any) -> None:
        for codec in self._parts(identifier, "request"):

            def send(value: object, operation: Operation, selected: Codec = codec) -> None:
                state = operation.transport.setdefault(identifier, {})
                if state.get("sent"):
                    raise AgentError(FailureCode.BUSY, "Request already sent in this invocation")
                request = self._assemble(
                    identifier, "request", interface.Request, selected, value, operation
                )
                if request is None:
                    return
                if not client.wait_for_service(
                    timeout_sec=min(5.0, max(0.0, operation.end - monotonic()))
                ):
                    raise AgentError(
                        FailureCode.TIMEOUT, "Service is unavailable", target=identifier
                    )
                state["sent"] = True
                future = client.call_async(request)

                def cleanup() -> None:
                    client.remove_pending_request(future)
                    future.cancel()

                operation.cleanup.append(cleanup)

                def complete(done: Any) -> None:
                    if operation.closed:
                        return
                    try:
                        response = done.result()
                        self._receive(identifier, "response", response, operation)
                    except Exception as error:
                        operation.fail(
                            AgentError(FailureCode.TRANSPORT, str(error), target=identifier)
                        )

                future.add_done_callback(complete)

            self.agent.register(codec.channel, send)

    def _action_client(self, endpoint: Mapping[str, Any], interface: Any, name: str) -> None:
        identifier = endpoint["id"]
        action_type = import_module("rclpy.action").ActionClient
        qos_options = self._action_qos(endpoint, server=False)

        def start_goal(message: Any, operation: Operation) -> None:
            action = action_type(
                self.scope.node,
                interface,
                name,
                callback_group=self.scope.group,
                **qos_options,
            )
            operation.cleanup.append(action.destroy)
            state = operation.transport[identifier]
            state["action"] = action
            if not action.wait_for_server(
                timeout_sec=min(5.0, max(0.0, operation.end - monotonic()))
            ):
                raise AgentError(
                    FailureCode.TIMEOUT, "Action server is unavailable", target=identifier
                )
            future = action.send_goal_async(
                message,
                feedback_callback=lambda feedback: self._receive(
                    identifier, "feedback", feedback.feedback, operation
                ),
            )

            def accepted(done: Any) -> None:
                try:
                    goal = done.result()
                    if operation.closed:
                        return
                    if not goal.accepted:
                        operation.fail(
                            AgentError(
                                FailureCode.TRANSPORT, "Action goal rejected", target=identifier
                            )
                        )
                        return
                    state["goal_handle"] = goal
                    if state.get("cancel_requested"):
                        state["cancel"] = goal.cancel_goal_async()
                    result = goal.get_result_async()

                    def completed(done_result: Any) -> None:
                        if operation.closed:
                            return
                        try:
                            response = done_result.result()
                            if response.status != 4:  # action_msgs/GoalStatus.STATUS_SUCCEEDED
                                code = (
                                    FailureCode.CANCELLED
                                    if response.status == 5
                                    else FailureCode.TRANSPORT
                                )
                                operation.fail(
                                    AgentError(code, "Action did not succeed", target=identifier)
                                )
                            else:
                                self._receive(identifier, "result", response.result, operation)
                        except Exception as error:
                            operation.fail(
                                AgentError(FailureCode.TRANSPORT, str(error), target=identifier)
                            )

                    result.add_done_callback(completed)
                except Exception as error:
                    if not operation.closed:
                        operation.fail(
                            AgentError(FailureCode.TRANSPORT, str(error), target=identifier)
                        )

            future.add_done_callback(accepted)

        for codec in self._parts(identifier, "goal"):

            def send(value: object, operation: Operation, selected: Codec = codec) -> None:
                state = operation.transport.setdefault(identifier, {})
                if state.get("sent"):
                    raise AgentError(FailureCode.BUSY, "Action goal already sent")
                goal = self._assemble(
                    identifier, "goal", interface.Goal, selected, value, operation
                )
                if goal is not None:
                    state["sent"] = True
                    start_goal(goal, operation)

            self.agent.register(codec.channel, send)
        for codec in self._parts(identifier, "cancel"):

            def cancel(value: object, operation: Operation) -> None:
                state = operation.transport.get(identifier, {})
                if not state.get("sent"):
                    raise AgentError(FailureCode.NOT_READY, "No action goal has been sent")
                state["cancel_requested"] = True
                goal = state.get("goal_handle")
                if goal is not None and "cancel" not in state:
                    state["cancel"] = goal.cancel_goal_async()

            self.agent.register(codec.channel, cancel)

    def _action_qos(self, endpoint: Mapping[str, Any], *, server: bool) -> dict[str, Any]:
        if not endpoint.get("qos"):
            return {}
        result = {
            name: self.qos(endpoint["qos"], "qos_profile_services_default")
            for name in (
                "goal_service_qos_profile",
                "result_service_qos_profile",
                "cancel_service_qos_profile",
            )
        }
        result["feedback_pub_qos_profile" if server else "feedback_sub_qos_profile"] = self.qos(
            endpoint["qos"], "qos_profile_default"
        )
        result["status_pub_qos_profile" if server else "status_sub_qos_profile"] = self.qos(
            endpoint["qos"], "qos_profile_action_status_default"
        )
        return result

    def _server(self, endpoint: Mapping[str, Any], interface: Any, name: str, qos: Any) -> None:
        identifier = endpoint["id"]
        action = endpoint["kind"] == "action"
        input_part, output_part = ("goal", "result") if action else ("request", "response")
        output_type = interface.Result if action else interface.Response

        def open_server(operation: Operation) -> None:
            state = operation.transport.setdefault(identifier, {})
            future = self.scope.runtime.executor.create_future()
            state["reply"] = future
            operation.cleanup.append(future.cancel)

            async def execute(request: Any, response: Any = None) -> Any:
                if state.get("received"):
                    failure = AgentError(
                        FailureCode.BUSY, "Native request already active", target=identifier
                    )
                    operation.fail(failure)
                    raise failure
                state["received"] = True
                if action:
                    state["goal_handle"] = request
                    request = request.request
                self._receive(identifier, input_part, request, operation)
                result = await future
                if result is None or operation.closed:
                    raise AgentError(
                        FailureCode.CLOSED,
                        "Server operation closed before response",
                        target=identifier,
                    )
                if action:
                    handle = state["goal_handle"]
                    if handle.is_cancel_requested:
                        handle.canceled()
                    else:
                        handle.succeed()
                return result

            if action:
                module = import_module("rclpy.action")

                def accept_goal(request: Any) -> Any:
                    if state.get("accepted"):
                        return module.GoalResponse.REJECT
                    state["accepted"] = True
                    return module.GoalResponse.ACCEPT

                def cancel_goal(handle: Any) -> Any:
                    cancel_codecs = self._parts(identifier, "cancel")
                    if not cancel_codecs:
                        return module.CancelResponse.REJECT
                    for selected in cancel_codecs:
                        self.agent.emit(selected.channel, selected.decode(handle), operation)
                    return module.CancelResponse.ACCEPT

                entity = module.ActionServer(
                    self.scope.node,
                    interface,
                    name,
                    execute_callback=execute,
                    goal_callback=accept_goal,
                    cancel_callback=cancel_goal,
                    callback_group=self.scope.group,
                    **self._action_qos(endpoint, server=True),
                )
                operation.cleanup.append(entity.destroy)
            else:
                entity = self.scope.node.create_service(
                    interface, name, execute, qos_profile=qos, callback_group=self.scope.group
                )
                operation.cleanup.append(lambda: self.scope.node.destroy_service(entity))

        self.agent.openers.setdefault(self._owner(identifier), []).append(open_server)
        for part in (output_part, "feedback") if action else (output_part,):
            message_type = interface.Feedback if part == "feedback" else output_type
            for codec in self._parts(identifier, part):

                def send(
                    value: object,
                    operation: Operation,
                    selected: Codec = codec,
                    cls: Any = message_type,
                ) -> None:
                    state = operation.transport.get(identifier, {})
                    if not state.get("received"):
                        raise AgentError(
                            FailureCode.NOT_READY,
                            "No native request has arrived",
                            target=identifier,
                        )
                    message = self._assemble(
                        identifier, selected.part, cls, selected, value, operation
                    )
                    if message is None:
                        return
                    if selected.part == "feedback":
                        state["goal_handle"].publish_feedback(message)
                    elif state["reply"].done():
                        raise AgentError(
                            FailureCode.BUSY, "Response already sent", target=identifier
                        )
                    else:
                        state["reply"].set_result(message)

                self.agent.register(codec.channel, send)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.scope.close()
