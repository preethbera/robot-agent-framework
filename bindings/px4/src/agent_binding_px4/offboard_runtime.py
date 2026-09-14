"""Scoped Offboard state machine; heartbeat ownership is explicit in the model."""

import math
from threading import RLock
from time import monotonic
from typing import Any

from agent_framework.runtime.agent import FactoryContext, Operation
from agent_framework.runtime.errors import AgentError, FailureCode

from .transport import CommandClient, Native, lane_for


class PositionComponent:
    def __init__(self, context: FactoryContext) -> None:
        self.context = context
        self.lock = RLock()
        self.native: Native | None = None
        self.command: CommandClient | None = None
        self.closed = False
        self.operation: Operation | None = None
        self.position_time = float("-inf")
        self.valid = False
        self.mode = -1
        self.started_at = 0.0
        self.warmup_at: float | None = None
        self.last_heartbeat = 0.0
        self.last_pulse = 0.0
        self.sent_mode = False
        self.active_reported = False
        self.setpoint: Any = None
        self.resources: list[tuple[Any, Any]] = []

    def start(self) -> None:
        if self.native is not None or self.closed:
            return
        self.native = Native(self.context)
        native = self.native
        self.command = CommandClient(native)
        self.setpoint_type, name, qos = native.entity("setpoint")
        self.publisher = native.node.create_publisher(self.setpoint_type, name, qos)
        self.resources.append((native.node.destroy_publisher, self.publisher))
        self.heartbeat_type, name, qos = native.entity("heartbeat")
        self.control_lane = lane_for(self.context.services.runtime, "offboard:" + name)
        self.heartbeat = native.node.create_publisher(self.heartbeat_type, name, qos)
        self.resources.append((native.node.destroy_publisher, self.heartbeat))
        for endpoint, callback in (("position", self.position), ("state", self.state)):
            interface, name, qos = native.entity(endpoint)
            subscription = native.node.create_subscription(
                interface,
                name,
                callback,
                qos,
                callback_group=self.context.services.group,
            )
            self.resources.append((native.node.destroy_subscription, subscription))
        timer = native.node.create_timer(0.1, self.tick, callback_group=self.context.services.group)
        self.resources.append((native.node.destroy_timer, timer))
        self.context.register(self.context.binding_id + ".setpoint", self.send)
        if self.context.configuration["liveness_owner"] == "application":
            self.context.register(self.context.binding_id + ".liveness", self.pulse)

    def position(self, message: Any) -> None:
        with self.lock:
            self.valid = bool(message.xy_valid and message.z_valid)
            self.position_time = monotonic()

    def state(self, message: Any) -> None:
        with self.lock:
            self.mode = int(message.nav_state)
            if self.operation and self.active_reported and self.mode != 14:
                self.context.emit(self.context.binding_id + ".status", "inactive", self.operation)
                self.stop(self.operation)
                return
            if self.operation and self.sent_mode and not self.active_reported and self.mode == 14:
                self.active_reported = True
                self.context.emit(self.context.binding_id + ".status", "active", self.operation)

    def send(self, value: Any, operation: Operation) -> None:
        with self.lock:
            assert self.native is not None
            if operation.transport.get(self.context.binding_id) == "stopped":
                raise AgentError(FailureCode.CLOSED, "Offboard session has ended")
            if not all(math.isfinite(v) for v in (value.x, value.y, value.z, value.yaw)):
                raise ValueError("Position and yaw must be finite")
            if not -math.pi <= value.yaw <= math.pi:
                raise ValueError("Yaw must be in [-pi, pi] radians")
            if not self.valid or monotonic() - self.position_time > 1.0:
                raise AgentError(FailureCode.NOT_READY, "Fresh valid local position is required")
            message = self.setpoint_type()
            message.timestamp = self.native.timestamp()
            message.position = [value.x, value.y, value.z]
            message.velocity = [math.nan] * 3
            message.acceleration = [math.nan] * 3
            message.jerk = [math.nan] * 3
            message.yaw = value.yaw
            message.yawspeed = math.nan
            if self.operation is not operation:
                if self.operation is not None:
                    raise AgentError(FailureCode.BUSY, "Offboard session still active")
                self.control_lane.acquire()
                self.operation = operation
                self.started_at = monotonic()
                self.warmup_at = None
                self.last_pulse = self.started_at
                self.sent_mode = self.active_reported = False
                operation.transport[self.context.binding_id] = "started"
                operation.cleanup.append(lambda: self.stop(operation))
                self.context.emit(self.context.binding_id + ".status", "warming_up", operation)
            self.setpoint = message
            self.publisher.publish(message)

    def _heartbeat(self) -> None:
        assert self.native is not None
        message = self.heartbeat_type()
        now = monotonic()
        if self.warmup_at is None or now - self.last_heartbeat > 0.4:
            self.warmup_at = now
        self.last_heartbeat = now
        message.timestamp = self.native.timestamp()
        message.position = True
        # PX4 requires a setpoint newer than position-control activation. Keep
        # the one cached target current across mode entry and explicit arming.
        if self.setpoint is not None:
            self.setpoint.timestamp = message.timestamp
            self.publisher.publish(self.setpoint)
        self.heartbeat.publish(message)

    def pulse(self, value: object, operation: Operation) -> None:
        with self.lock:
            if self.operation is not operation:
                raise AgentError(FailureCode.NOT_READY, "Send an initial position setpoint first")
            if monotonic() - self.last_pulse > 0.4:
                error = AgentError(FailureCode.TIMEOUT, "Offboard heartbeat interrupted")
                operation.fail(error)
                self.stop(operation)
                raise error
            self.last_pulse = monotonic()
            self._heartbeat()

    def tick(self) -> None:
        try:
            self._tick()
        except Exception as error:
            with self.lock:
                if self.operation is not None:
                    self.operation.fail(AgentError(FailureCode.TRANSPORT, str(error)))
                    self.stop(self.operation)

    def _tick(self) -> None:
        with self.lock:
            operation = self.operation
            if operation is None or self.closed:
                return
            now = monotonic()
            if operation.closed:
                self.stop(operation)
                return
            if now >= operation.end or not self.valid or now - self.position_time > 1.0:
                operation.fail(
                    AgentError(FailureCode.TIMEOUT, "Offboard deadline/position expired")
                )
                self.stop(operation)
                return
            if self.sent_mode and not self.active_reported and now - self.started_at > 7.0:
                operation.fail(AgentError(FailureCode.TIMEOUT, "Offboard activation not observed"))
                self.stop(operation)
                return
            if self.sent_mode and now - self.last_heartbeat > 0.4:
                operation.fail(AgentError(FailureCode.TIMEOUT, "Offboard heartbeat interrupted"))
                self.stop(operation)
                return
            if self.context.configuration["liveness_owner"] == "binding":
                self._heartbeat()
            elif now - self.last_pulse > 0.4:
                operation.fail(AgentError(FailureCode.TIMEOUT, "Application liveness expired"))
                self.stop(operation)
                return
            if not self.sent_mode and self.warmup_at is not None and now - self.warmup_at >= 1.1:
                assert self.command is not None
                try:
                    self.command.send(176, (1.0, 6.0), operation, self.acknowledged)
                    self.sent_mode = True
                except AgentError as error:
                    operation.fail(error)
                    self.stop(operation)

    def acknowledged(self, status: str) -> None:
        with self.lock:
            operation = self.operation
            if operation is None:
                return
            self.context.emit(self.context.binding_id + ".ack", status, operation)
            if status != "accepted":
                self.stop(operation)

    def stop(self, operation: Operation) -> None:
        with self.lock:
            if self.operation is operation:
                self.control_lane.release()
                operation.transport[self.context.binding_id] = "stopped"
                self.operation = None
                self.setpoint = None

    def close(self) -> None:
        with self.lock:
            if self.closed:
                return
            self.closed = True
            if self.operation is not None:
                self.stop(self.operation)
            if self.command:
                self.command.close()
            for destroy, entity in reversed(self.resources):
                destroy(entity)
            self.resources.clear()


def create_component(context: FactoryContext) -> PositionComponent:
    return PositionComponent(context)
