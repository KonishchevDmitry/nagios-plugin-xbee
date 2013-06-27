"""Contains various core classes and functions."""

from __future__ import unicode_literals


class Error(Exception):
    """The base class for exceptions that our code throws."""

    def __init__(self, error, *args):
        super(Error, self).__init__(error.format(*args) if args else error)


class LogicalError(Exception):
    """Thrown in all code that must not be executed."""

    def __init__(self):
        super(LogicalError, self).__init__("Logical error.")
