"""Native service transport for ArduPilot operations."""

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
    """ArduPilot service has one pending request; serialize per runtime/endpoint."""

    def __init__(self) -> None:
        self.lock = RLock()
        self.pending = False
        self.uncertain = False

    def acquire(self, *, force: bool = False) -> None:
        with self.lock:
            if self.uncertain and not force:
                raise AgentError(
                    FailureCode.NOT_READY,
                    "Previous ArduPilot command outcome is uncertain; recreate runtime",
                )
            if self.pending and not force:
                raise AgentError(FailureCode.BUSY, "ArduPilot command service is busy")
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


class ServiceClient:
    """Generic ArduPilot service client with timeout and lane coordination."""

    def __init__(self, native: Native, endpoint_id: str) -> None:
        self.native = native
        self.context = native.context
        self.interface, name, qos = native.entity(endpoint_id)
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
        self.timer = native.node.create_timer(
            0.05, self.check, callback_group=self.context.services.group
        )

    def _prepare_send(self, operation: Operation, is_emergency: bool) -> None:
        if self.closed:
            raise AgentError(FailureCode.CLOSED, "ArduPilot service client closed")
        ready = getattr(self.client, "service_is_ready", None)
        if ready is None or not ready():
            if not self.client.wait_for_service(
                timeout_sec=min(1.0, max(0.0, operation.end - monotonic()))
            ):
                raise AgentError(FailureCode.TIMEOUT, "ArduPilot service unavailable")
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

    def _make_done_callback(
        self, operation: Operation, completed: Callable[[Any], None]
    ) -> Callable[[Any], None]:
        def done(result: Any) -> None:
            with self.lock:
                if self.pending is None or self.pending[0] is not result:
                    return
                self.pending = None
                try:
                    reply = result.result()
                    self.lane.release()
                except Exception as error:
                    self.lane.release(uncertain=True)
                    operation.fail(AgentError(FailureCode.TRANSPORT, str(error)))
                    return
            if not operation.closed:
                completed(reply)

        return done

    def _stop_timer(self) -> None:
        if self.timer is not None:
            self.native.node.destroy_timer(self.timer)
            self.timer = None

    def send(
        self,
        request_fields: dict[str, Any],
        operation: Operation,
        completed: Callable[[Any], None],
        *,
        force: bool = False,
    ) -> None:
        is_emergency = (
            force
            or request_fields.get("arm") is False
            or request_fields.get("mode") in (5, 6, 9)
        )
        with self.lock:
            self._prepare_send(operation, is_emergency)
            try:
                request = self.interface.Request()
                for key, value in request_fields.items():
                    setattr(request, key, value)
                future = self.client.call_async(request)
                self.pending = future, operation, min(operation.end, monotonic() + 5.0)
            except Exception:
                self.lane.release()
                raise

            future.add_done_callback(self._make_done_callback(operation, completed))

    def check(self) -> None:
        with self.lock:
            if self.pending is None:
                return
            future, operation, end = self.pending
            if operation.closed or monotonic() >= end:
                self.pending = None
                self.lane.release(uncertain=True)
                self.client.remove_pending_request(future)
                future.cancel()
                if not operation.closed:
                    operation.fail(
                        AgentError(
                            FailureCode.TIMEOUT,
                            "ArduPilot service acknowledgement timed out",
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
            self.native.node.destroy_timer(self.timer)
            self.native.node.destroy_client(self.client)

