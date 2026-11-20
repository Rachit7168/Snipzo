"""User-facing errors raised by the Snipzo pipeline."""


class SnipzoError(Exception):
    """An error that should be reported to the user and stop the command."""
