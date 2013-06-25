from pcore import str

class Error(Exception):
    """The base class for all exceptions that our code throws."""

    def __init__(self, error, *args):
        Exception.__init__(self, str(error).format(*args) if len(args) else str(error))
        self.code = "Error"



class LogicalError(Exception):
    """Thrown in all code that must not be executed."""

    def __init__(self):
        Exception.__init__(self, "Logical error.")
