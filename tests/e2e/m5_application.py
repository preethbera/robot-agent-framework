"""SITL application: only generated Agent API and Python standard-library imports."""

import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from threading import Event, Thread

from agent_px4_agent import (  # type: ignore[import-not-found]
    Agent,
    AgentError,
    FailureCode,
    Payload_arm_request,
    Payload_offboard_setpoint,
    Payload_orbit_request,
)


def until(condition: Callable[[], bool], timeout: float = 20.0) -> None:
    end = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < end, "Observed state did not reach requested condition"
        time.sleep(0.1)


@contextmanager
def liveness(send: Callable[[], None], enabled: bool) -> Iterator[Callable[[], None]]:
    stopping = Event()
    exiting = Event()
    failures: list[Exception] = []

    def run_pulses() -> None:
        while not stopping.is_set():
            try:
                send()
            except Exception as error:
                # An observed mode exit may end the component before this
                # worker stops. Only accept that race after an explicit exit
                # request; the main thread still verifies the requested mode.
                if (
                    exiting.is_set()
                    and isinstance(error, AgentError)
                    and error.code in (FailureCode.CLOSED, FailureCode.NOT_READY)
                ):
                    return
                failures.append(error)
                return
            stopping.wait(0.1)

    worker = Thread(target=run_pulses)
    if enabled:
        worker.start()
    try:
        yield exiting.set
    finally:
        stopping.set()
        if enabled:
            worker.join(timeout=2)
            assert not worker.is_alive()
    assert not failures, failures


def run(application_owned: bool = False) -> None:
    with Agent(instance_id="sitl", namespace="/m5") as agent:
        assert agent.armed.get(timeout=30) == "disarmed"
        agent.position.get(timeout=10)
        agent.velocity.get(timeout=10)
        # Allow the simulator's estimator to finish initialization. The runtime
        # additionally refuses control without fresh, valid position estimates.
        time.sleep(5)
        with agent.offboard.start() as session:
            session.setpoint.send(Payload_offboard_setpoint(x=0.0, y=0.0, z=-3.0, yaw=0.0))
            with liveness(
                lambda: session.liveness.send(Payload_arm_request()), application_owned
            ) as begin_exit:
                assert session.ack.read(timeout=10) == "accepted"
                until(lambda: agent.flight_mode.get() == "offboard")
                with agent.arm.start() as call:
                    call.request.send(Payload_arm_request())
                    assert call.ack.read() == "accepted"
                until(lambda: agent.armed.get() == "armed")
                until(lambda: agent.position.get().z < -2.0, timeout=30)
                begin_exit()
                with agent.hold.start() as call:
                    call.request.send(Payload_arm_request())
                    assert call.ack.read() == "accepted"
                until(lambda: agent.flight_mode.get() == "hold")
        with agent.orbit.start() as call:
            call.request.send(
                Payload_orbit_request(
                    radius_m=10.0,
                    speed_m_s=1.0,
                    latitude_deg=47.397742,
                    longitude_deg=8.545594,
                    altitude_m=491.0,
                )
            )
            assert call.ack.read() == "accepted"
        until(lambda: agent.flight_mode.get() == "orbit")
        time.sleep(2)
        with agent.land.start() as call:
            call.request.send(Payload_arm_request())
            assert call.ack.read() == "accepted"
        until(lambda: agent.flight_mode.get() == "land")
        until(lambda: agent.landed.get(), timeout=40)
        with agent.disarm.start() as call:
            call.request.send(Payload_arm_request())
            assert call.ack.read() == "accepted"
        until(lambda: agent.armed.get() == "disarmed")
    print("M5 generated application: all Properties, commands and Offboard passed", flush=True)


if __name__ == "__main__":
    run(len(sys.argv) > 1 and sys.argv[1] == "application")
