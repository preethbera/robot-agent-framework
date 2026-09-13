"""Explicit build-time binding failures."""


class BindingError(ValueError):
    """Invalid installed binding or binding configuration."""


class MissingBindingError(BindingError):
    """A referenced package or binding definition is unavailable."""


class IncompatibleBindingError(BindingError):
    """A provider does not support this Binding API version."""
