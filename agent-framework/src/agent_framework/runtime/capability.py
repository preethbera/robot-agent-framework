"""Base for statically generated typed Capability handles."""

from .agent import AgentRuntime


class Capability:
    def __init__(self, agent: AgentRuntime) -> None:
        self._agent = agent
