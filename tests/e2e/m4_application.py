"""Application-side acceptance: imports only its generated Agent-facing API."""

import time

from agent_test_agent import (  # type: ignore[import-not-found]
    Agent,
    AgentError,
    FailureCode,
    Runtime,
)


def run() -> None:
    runtime = Runtime()
    try:
        with (
            Agent(instance_id="m4_a", runtime=runtime) as first,
            Agent(instance_id="m4_b", runtime=runtime) as second,
        ):
            assert first.temperature.get(timeout=5) == 21.5
            assert second.temperature.get(timeout=5) == 31.5
            assert first.command.invoke(20.0, timeout=5) == 40.0
            try:
                first.command.invoke(81.0)
            except AgentError as error:
                assert error.code == FailureCode.INVALID_VALUE
            else:
                raise AssertionError("constraint was not enforced")
            try:
                first.command.invoke(13.0, timeout=0.05)
            except AgentError as error:
                assert error.code == FailureCode.TIMEOUT
            else:
                raise AssertionError("slow invocation did not time out")
            assert first.command.invoke(14.0, timeout=5) == 28.0
            with first.lidar_stream.start(capacity=4) as session:
                assert session.output.read(timeout=5) == 7.0
                session.liveness.send(1.0)
            with first.lidar_stream.start(capacity=1) as session:
                time.sleep(0.8)
                try:
                    session.output.read(timeout=1)
                except AgentError as error:
                    assert error.code == FailureCode.OVERFLOW
                else:
                    raise AssertionError("stream overflow was not explicit")
            with first.lidar_stream.start() as session:
                assert session.output.read(timeout=5) == 7.0
    finally:
        runtime.close()
