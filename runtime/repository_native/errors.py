"""Typed launcher failures with stable user-facing messages."""


class HardEngError(RuntimeError):
    """A startup failure that should stop before the agent runs."""


class ConfigurationError(HardEngError):
    """Repository or global Hard Eng state is incomplete or unsafe."""


class FetchError(HardEngError):
    """The Hard Eng copy could not be fetched or activated."""
