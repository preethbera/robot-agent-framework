"""Explicit failures before ROS2 realization or runtime startup."""


class ResolutionError(ValueError):
    """The requested semantics cannot be resolved consistently."""


class MandatoryRequirementError(ResolutionError):
    """An Agent/configuration attempts to weaken a binding requirement."""
