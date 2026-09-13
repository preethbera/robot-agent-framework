"""Scoped session handle; close releases its delivery buffers and operation resources."""

from .invocation import Invocation


class Session(Invocation):
    """A bounded stream session, explicitly closed or used as a context manager."""
