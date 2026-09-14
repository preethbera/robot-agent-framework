from types import SimpleNamespace

import pytest
from agent_framework.runtime.channel import Buffer
from agent_framework.runtime.errors import AgentError, FailureCode


def test_measured_queue_residence_and_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = SimpleNamespace(now=1.0)
    monkeypatch.setattr("agent_framework.runtime.channel.monotonic", lambda: clock.now)
    buffer: Buffer[int] = Buffer(2)
    assert buffer.statistics().latency is None
    buffer.put(1)
    clock.now = 1.25
    assert buffer.statistics().queue_depth == 1
    assert buffer.read() == 1
    assert buffer.statistics().latency == 0.25
    assert buffer.statistics().queue_depth == 0
    for value in (1, 2, 3, 4):
        buffer.put(value)
    assert buffer.statistics().dropped_samples == 4
    assert buffer.statistics().queue_depth == 0
    with pytest.raises(AgentError) as failure:
        buffer.read()
    assert failure.value.code == FailureCode.OVERFLOW
