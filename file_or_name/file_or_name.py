import logging
import inspect
from functools import wraps
from contextlib import contextmanager
from typing import Callable, Any, List, Dict, Tuple


__all__ = ["file_or_name"]
LOGGER = logging.getLogger("file_or_name")
UTF_8 = "utf-8"


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


@contextmanager
def open_files(files: Dict[str, str], function: Callable, *args: List[Any], **kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Open files that are arguments to this function call and close ones we opened after the call.

    :param files: A mapping of argument name to file mode. This should include all arguments that are files
    :param function: The user defined function we are opening these files for
    :param args: A list of positional args function was called with
    :param kwargs: A dict of keyword args function was called with
    :returns: A dict mapping argument names to argument values with the opened files inserted.
        function should now be called with this dict ** unpacked.
    """
    to_close = []
    call_args = inspect.getcallargs(function, *args, **kwargs)
    for file_name, mode in files.items():
        LOGGER.debug("Opening file %s in mode %s", file_name, mode)
        if file_name not in call_args:
            raise ValueError(f"Argument {file_name} is missing and expected to be opened in {mode} mode.")
        if isinstance(call_args[file_name], str):
            call_args[file_name] = open(call_args[file_name], mode=mode, encoding=None if "b" in mode else UTF_8)
            to_close.append(call_args[file_name])
    yield call_args
    for f in to_close:
        LOGGER.debug("Closing parameter file %s", f.name)
        f.close()


def get_first_parameter(function: Callable) -> str:
    """Get the name of the first parameter of a function.

    :param function: The function we want the name of the first parameter of
    :returns: The name of the first parameters
    """
    sig = inspect.signature(function)
    return list(sig.parameters.keys())[0]


@parameterize
def file_or_name(function: Callable, **kwargs: Dict[str, str]) -> Callable:
    """Transparent allow arguments to be either strings or open files.

    kwargs are of the form name=mode, This is used to create a mapping of arguments
    to the mode that file should be opened with, for example if the argument named
    wf should be opened in write mode you would call
        `@file_or_name(wf='w')`

    If there are no kwargs it is assumed the first argument is a file that will be
    opened in read mode "r"

    If you need a file to be opened with extra arguments, for example `newline=''`
    for files the stdlib csv writer, you should manually open the file and pass
    the resulting file object in.
    """
    files = kwargs
    # If no file modes are specified in the kwargs we set the first argument to be opened in read mode
    if not files:
        first = get_first_parameter(function)
        LOGGER.debug("No file parameters provided, using %s='r'", first)
        files[first] = "r"
    to_close = []
    # We
    if inspect.isgeneratorfunction(function):

        @wraps(function)
        def open_arg_files(*args, **kwargs):
            with open_files(files, function, *args, **kwargs) as call_args:
                yield from function(**call_args)

    else:

        @wraps(function)
        def open_arg_files(*args, **kwargs):
            with open_files(files, function, *args, **kwargs) as call_args:
                return function(**call_args)

    return open_arg_files
