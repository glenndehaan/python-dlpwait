"""DLPWait Client Exceptions."""

class DLPWaitError(Exception):
    """Base exception for DLPWait client."""


class DLPWaitConnectionError(DLPWaitError):
    """DLPWait connection exception."""
