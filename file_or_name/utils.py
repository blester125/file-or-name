import os
import logging
import inspect
from functools import wraps
from typing import Callable, Optional
from tempfile import NamedTemporaryFile


__all__ = ["parameterize", "get_first_parameter", "ShadowPage"]
LOGGER = logging.getLogger("file_or_name")


def parameterize(function: Callable) -> Callable:
    """A decorator for decorators that allow them to be called without parentheses if no kwargs are given.

    Args:
        function: A decorator that we want to use with either ``@function`` or ``@function(kwarg=kwvalue)``

    Returns:
        A decorated decorator that can be used with or without parentheses
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

        @wraps(function)
        def with_params(wrappe):
            return function(wrappe, *args, **kwargs)

        return with_params

    return decorator


def get_first_parameter(function: Callable) -> str:
    """Get the name of the first parameter of a function.

    Args:
        function: The function whose first parameter name we want.

    Returns:
        The name of the first parameter.
    """
    sig = inspect.signature(function)
    return list(sig.parameters.keys())[0]


class ShadowPage:
    """Store updates to a copy of the output file and swing pointers for an atomic write.

    Note:
        In some environments like Kubernetes this is not safe to use when the file we are shadowing
        is in a PersistentVolumeClaim. The temporary file lives in the containers file system and
        in some configurations Kubernetes will block copying files from the container local file
        system into the PVC file system.

    Args:
        path: The file that we are shadowing.
        mode: The mode we should open the shadow file in.
        dir: The directory in which the shadow file should be created.
        encoding: The file type encoding the shadow file should be opened in.
    """

    def __init__(self, path: str, mode: str = "wb", dir: Optional[str] = None, encoding: Optional[str] = None):
        self.path = path
        # Don't try to delete the temp file when cleaning up, it will either be removed in the
        # swing to the real file or it should be left for debugging
        self.temp_file = NamedTemporaryFile(mode=mode, delete=False, dir=dir, encoding=encoding)
        LOGGER.debug("Opening shadow file for %s at %s", self.path, self.temp_file.name)

    def __enter__(self):
        """Go the normal thing temp files do when entering a context block."""
        self.temp_file.__enter__()
        return self

    def write(self, *args, **kwargs):
        """Proxy writes to the temp file."""
        return self.temp_file.write(*args, **kwargs)

    def __exit__(self, exc, value, tb):
        # If we exited this context manager normally swing the pointer to the real path
        if exc is None:
            # Try to set the permission on the temp file to match the real file
            try:
                stat = os.stat(self.path)
                os.chown(self.temp_file.name, stat.st_uid, stat.st_gid)
                os.chmod(self.temp_file.name, stat.st_mode)
            except FileNotFoundError:
                pass
            os.replace(self.temp_file.name, self.path)
            LOGGER.debug("Replacing %s with shadow file %s", self.path, self.temp_file.name)
        # If we found an error don't try to replace the old file
        else:
            LOGGER.debug("Context closed do to %s rolling back update.", exc.__name__)
        # Normal tempfile cleanup
        self.temp_file.__exit__(exc, value, tb)
