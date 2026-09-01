"""Typed launcher failures with stable user-facing messages."""


class HardEngError(RuntimeError):
    """A startup failure that should stop before the agent runs."""


class ConfigurationError(HardEngError):
    """Repository or global Hard Eng state is incomplete or unsafe."""


class ReleaseError(HardEngError):
    """A release could not be selected, verified, or activated."""


class ReleaseUnavailable(ReleaseError):
    """GitHub could not be reached, so an already verified cache may be used."""
