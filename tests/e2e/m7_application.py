"""Combined SITL and sensing application using generated Agent types only."""

import sys
import time
from pathlib import Path
from threading import Event, Thread
from typing import cast

from agent_framework.deployment import Deployment, load_deployment_spec
from agent_sensor_drone import (  # type: ignore[import-not-found]
    Agent,
    AgentError,
    FailureCode,
    Payload_arm_request,
)


def main() -> None:
    spec = load_deployment_spec(Path(sys.argv[2]))
    with Deployment(spec, Path(sys.argv[1]), agent_types={"sensor_drone": Agent}) as deployment:
        first = cast(Agent, deployment["drone_instance_1"])
        second = cast(Agent, deployment["drone_instance_2"])
        assert first.runtime is second.runtime
        assert first.lidar_status.get(timeout=15) == 0
        assert second.lidar_status.get(timeout=15) == 1
        assert first.armed.get(timeout=30) == "disarmed"
        assert first.landed.get(timeout=10)
        with first.scan.start(capacity=32) as scan1, second.scan.start(capacity=32) as scan2:
            failures = []
            stopping = Event()
            counts = [0, 0]

            def consume() -> None:
                try:
                    while not stopping.is_set():
                        for i, channel in enumerate((scan1.scan, scan2.scan)):
                            value = channel.read(timeout=5)
                            assert len(value.ranges) == 4096
                            assert set(value.ranges) == {float((i + 1) * 10)}
                            counts[i] += 1
                except Exception as error:
                    failures.append(error)

            worker = Thread(target=consume)
            worker.start()
            try:
                time.sleep(5)
                with first.arm.start() as call:
                    call.request.send(Payload_arm_request())
                    assert call.ack.read(timeout=10) == "accepted"
                end = time.monotonic() + 10
                while first.armed.get() != "armed":
                    assert time.monotonic() < end
                    time.sleep(0.05)
                with first.disarm.start() as call:
                    call.request.send(Payload_arm_request())
                    assert call.ack.read(timeout=10) == "accepted"
                end = time.monotonic() + 10
                while first.armed.get() != "disarmed":
                    assert time.monotonic() < end
                    time.sleep(0.05)
            finally:
                stopping.set()
                worker.join(timeout=6)
                assert not worker.is_alive()
            assert not failures, failures
            assert min(counts) >= 50, counts
            for channel in (scan1.scan, scan2.scan):
                stats = channel.statistics
                assert stats.latency is not None and stats.latency >= 0
                assert stats.dropped_samples == 0
                assert 0 <= stats.queue_depth <= 32
        with first.scan.start(capacity=16) as scan:
            end = time.monotonic() + 5
            while scan.scan.statistics.queue_depth == 0:
                assert time.monotonic() < end
                time.sleep(0.01)
            time.sleep(0.1)
            scan.scan.read(timeout=1)
            latency = scan.scan.statistics.latency
            assert latency is not None and latency >= 0.1
        # Deliberately stall the consumer: overflow must fail, not grow or hide loss.
        with first.scan.start(capacity=2) as scan:
            end = time.monotonic() + 5
            while scan.scan.statistics.dropped_samples == 0:
                assert time.monotonic() < end
                time.sleep(0.05)
            stats = scan.scan.statistics
            assert stats.dropped_samples >= 3 and stats.queue_depth == 0
            try:
                scan.scan.read(timeout=1)
            except AgentError as error:
                assert error.code == FailureCode.OVERFLOW
            else:
                raise AssertionError("overflow was hidden")
        with first.scan.start() as scan:
            assert len(scan.scan.read(timeout=5).ranges) == 4096
    print("M7 combined generated API: PX4 control, isolated streams and overflow passed")


if __name__ == "__main__":
    main()
