"""Build-time ROS2 description failures are resolution errors."""

from agent_framework.resolution.errors import ResolutionError


class RealizationError(ResolutionError):
    """Invalid binding realization or Agent ROS2 override."""
