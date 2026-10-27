"""Native service transport and bounded coordination shared by PX4 operations."""

from collections.abc import Callable
from importlib import import_module
from threading import RLock
from time import monotonic
from typing import Any
from weakref import WeakKeyDictionary

from agent_framework.ros2.runtime import endpoint_name
from agent_framework.runtime.agent import FactoryContext, Operation
from agent_framework.runtime.errors import AgentError, FailureCode


class Lane:
    """PX4's native service has one pending request; serialize per runtime/endpoint."""

    def __init__(self) -> None:
        self.lock = RLock()
        self.pending = False
        self.uncertain = False

    def acquire(self, *, force: bool = False) -> None:
        with self.lock:
            if self.uncertain and not force:
                raise AgentError(
                    FailureCode.NOT_READY,
                    "Previous PX4 command outcome is uncertain; recreate runtime",
                )
            if self.pending and not force:
                raise AgentError(FailureCode.BUSY, "PX4 command service is busy")
            self.pending = True
            if force:
                self.uncertain = False

    def release(self, *, uncertain: bool = False) -> None:
        with self.lock:
            self.pending = False
            self.uncertain |= uncertain


# Coordination only, never ROS resources or Agent instances. Entries disappear
# with their framework runtime, and are bounded by its configured endpoints.
_LANES: WeakKeyDictionary[Any, dict[str, Lane]] = WeakKeyDictionary()
_LANES_LOCK = RLock()


def lane_for(runtime: Any, name: str) -> Lane:
    with _LANES_LOCK:
        return _LANES.setdefault(runtime, {}).setdefault(name, Lane())


class Native:
    def __init__(self, context: FactoryContext) -> None:
        self.context = context
        self.node = context.services.node
        self.endpoints = {
            item["id"].rsplit(".", 1)[-1]: item for item in context.realization["endpoints"]
        }

    def entity(self, identifier: str) -> tuple[Any, str, Any]:
        endpoint = self.endpoints[identifier]
        package, kind, name = endpoint["interface_type"].split("/")
        interface = getattr(import_module(package + "." + kind), name)
        native = endpoint_name(endpoint, self.context.instance_id, self.context.namespace)
        policies = import_module("rclpy.qos")
        qos = policies.QoSProfile(
            depth=endpoint["qos"]["depth"],
            history=policies.HistoryPolicy.KEEP_LAST,
            reliability=(
                policies.ReliabilityPolicy.RELIABLE
                if endpoint["qos"]["reliability"] == "reliable"
                else policies.ReliabilityPolicy.BEST_EFFORT
            ),
            durability=policies.DurabilityPolicy.VOLATILE,
        )
        return interface, native, qos

    def timestamp(self) -> int:
        return int(self.node.get_clock().now().nanoseconds // 1000)


_ACKS = {
    0: "accepted",
    1: "temporarily_rejected",
    2: "denied",
    3: "unsupported",
    4: "failed",
    5: "in_progress",
    6: "cancelled",
}


class CommandClient:
    def __init__(self, native: Native) -> None:
        self.native = native
        self.context = native.context
        self.interface, name, qos = native.entity("command")
        self.client = native.node.create_client(
            self.interface,
            name,
            qos_profile=qos,
            callback_group=self.context.services.group,
        )
        self.lane = lane_for(self.context.services.runtime, name)
        self.lock = RLock()
        self.pending: tuple[Any, Operation, float] | None = None
        self.closed = False
        self.timer: Any = None

    def _stop_timer(self) -> None:
        if self.timer is not None:
            self.native.node.destroy_timer(self.timer)
            self.timer = None

    def _prepare_send(self, operation: Operation, is_emergency: bool) -> None:
        if self.closed:
            raise AgentError(FailureCode.CLOSED, "PX4 command client closed")
        ready = getattr(self.client, "service_is_ready", None)
        if ready is None or not ready():
            if not self.client.wait_for_service(
                timeout_sec=min(1.0, max(0.0, operation.end - monotonic()))
            ):
                raise AgentError(FailureCode.TIMEOUT, "PX4 command service unavailable")
        if is_emergency and self.pending is not None:
            prev_future, prev_op, _ = self.pending
            self.pending = None
            self._stop_timer()
            if hasattr(self.client, "remove_pending_request"):
                self.client.remove_pending_request(prev_future)
            prev_future.cancel()
            if not prev_op.closed:
                prev_op.fail(AgentError(FailureCode.CANCELLED, "Preempted by emergency command"))
        self.lane.acquire(force=is_emergency)

    def _build_request(self, command: int, parameters: tuple[float, ...]) -> Any:
        request = self.interface.Request()
        message = request.request
        message.timestamp = self.native.timestamp()
        message.command = command
        message.target_system = self.context.instance_configuration.get(
            "target_system", self.context.configuration["target_system"]
        )
        message.target_component = self.context.instance_configuration.get(
            "target_component", self.context.configuration["target_component"]
        )
        message.source_system = 245
        message.source_component = 191
        message.from_external = True
        padded = (*parameters, *(0.0 for _ in range(7 - len(parameters))))
        (
            message.param1,
            message.param2,
            message.param3,
            message.param4,
            message.param5,
            message.param6,
            message.param7,
        ) = padded
        return request

    def _make_done_callback(
        self, command: int, operation: Operation, completed: Callable[[str], None]
    ) -> Callable[[Any], None]:
        def done(result: Any) -> None:
            with self.lock:
                if self.pending is None or self.pending[0] is not result:
                    return
                self.pending = None
                self._stop_timer()
                try:
                    reply = result.result().reply
                    if reply.command != command:
                        raise ValueError("PX4 acknowledgement command mismatch")
                    status = _ACKS.get(reply.result, "unknown")
                    self.lane.release(uncertain=status in ("in_progress", "unknown"))
                except Exception as error:
                    self.lane.release(uncertain=True)
                    operation.fail(AgentError(FailureCode.TRANSPORT, str(error)))
                    return
            if not operation.closed:
                completed(status)

        return done

    def send(
        self,
        command: int,
        parameters: tuple[float, ...],
        operation: Operation,
        completed: Callable[[str], None],
        *,
        force: bool = False,
    ) -> None:
        is_emergency = (
            force
            or command in (21, 176)
            or (command == 400 and bool(parameters) and parameters[0] == 0.0)
        )
        with self.lock:
            self._prepare_send(operation, is_emergency)
            try:
                request = self._build_request(command, parameters)
                future = self.client.call_async(request)
                self.pending = future, operation, min(operation.end, monotonic() + 5.0)
                if self.timer is None:
                    self.timer = self.native.node.create_timer(
                        0.05, self.check, callback_group=self.context.services.group
                    )
            except Exception:
                self.lane.release()
                raise

            future.add_done_callback(self._make_done_callback(command, operation, completed))

    def check(self) -> None:
        with self.lock:
            if self.pending is None:
                self._stop_timer()
                return
            future, operation, end = self.pending
            if operation.closed or monotonic() >= end:
                self.pending = None
                self._stop_timer()
                self.lane.release(uncertain=True)
                self.client.remove_pending_request(future)
                future.cancel()
                if not operation.closed:
                    operation.fail(
                        AgentError(
                            FailureCode.TIMEOUT,
                            "PX4 command acknowledgement timed out; observed state is independent",
                        )
                    )

    def close(self) -> None:
        with self.lock:
            if self.closed:
                return
            self.closed = True
            if self.pending:
                future, _, _ = self.pending
                self.pending = None
                self.lane.release(uncertain=True)
                self.client.remove_pending_request(future)
                future.cancel()
            self._stop_timer()
            self.native.node.destroy_client(self.client)
