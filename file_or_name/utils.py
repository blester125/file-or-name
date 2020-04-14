import os
import logging
import inspect
from typing import Callable
from functools import wraps
from tempfile import NamedTemporaryFile


__all__ = ["parameterize", "get_first_parameter", "ShadowPage"]
LOGGER = logging.getLogger("file_or_name")


def parameterize(function: Callable) -> Callable:
    """Allow a decorator to be called without parentheses if no kwargs are given.

    parameterize is a decorator, function is also a decorator.
    """

    @wraps(function)
    def decorator(*args, **kwargs):
        """If a decorator is called with only the wrapping function just execute the real decorator.
           Otherwise return a lambda that has the args and kwargs partially applied and read to take a function as an argument.

        *args, **kwargs are the arguments that the decorator we are parameterizing is called with.

        the first argument of *args is the actual function that will be wrapped
        """
        if len(args) == 1 and not kwargs and callable(args[0]):
            return function(args[0])
        return lambda wrappee: function(wrappee, *args, **kwargs)

    return decorator


def get_first_parameter(function: Callable) -> str:
    """Get the name of the first parameter of a function.

    :param function: The function we want the name of the first parameter of
    :returns: The name of the first parameters
    """
    sig = inspect.signature(function)
    return list(sig.parameters.keys())[0]


class ShadowPage:
    def __init__(self, path, mode="wb", delete=False, dir=None, encoding=None):
        self.path = path
        self.temp_file = NamedTemporaryFile(mode=mode, delete=delete, dir=dir, encoding=encoding)
        LOGGER.debug("Opening shadow file for %s at %s", self.path, self.temp_file.name)

    def __enter__(self):
        self.temp_file.__enter__()
        return self

    def write(self, *args, **kwargs):
        return self.temp_file.write(*args, **kwargs)

    def __exit__(self, exc, value, tb):
        try:
            stat = os.stat(self.path)
            os.chown(self.temp_file.name, stat.st_uid, stat.st_gid)
            os.chmod(self.temp_file.name, stat.st_mode)
        except FileNotFoundError:
            pass
        if exc is None:
            os.replace(self.temp_file.name, self.path)
            LOGGER.debug("Replacing %s with shadow file %s", self.path, self.temp_file.name)
        else:
            LOGGER.debug("Context closed do to %s rolling back update.", exc.__name__)
        self.temp_file.__exit__(exc, value, tb)
