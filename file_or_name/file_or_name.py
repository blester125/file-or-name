import logging
import inspect
import pathlib
from functools import wraps
from contextlib import contextmanager, ExitStack
from typing import Callable, Any, List, Dict, Tuple
from file_or_name.utils import parameterize, get_first_parameter, ShadowPage


__all__ = ["file_or_name"]
LOGGER = logging.getLogger("file_or_name")
UTF_8 = "utf-8"


@contextmanager
def open_files(files: Dict[str, str], function: Callable, *args: List[Any], **kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Automatically open files specified by certain arguments and handle cleaning them up.

    Args:
        files: A mapping of argument to file mode. When the decorated function is called all parameters in this
            mapping will be checked. If the parameter is a string (of a pathlib object) it will be opened in
            the mode specified by the value in this mapping.
        function: The user defined function that we are managing the opening of files for.
        args: A list of positional arguments that that the function is to be called with.
        kwargs: A dictionary of keyword arguments that the function is to be called with.

    Yields:
        A dictionary mapping argument names to values with the string values for arguments in the files mapping
        replaced by the opened file. The user defined function should be called by ``**`` unpacking this mapping.

    Raises:
        ValueError: When shadow paging is requested for a non write-mode file.
    """
    # Get the arguments for this function in a Dict[str, Any] format that maps parameter name to argument value
    call_args = inspect.getcallargs(function, *args, **kwargs)
    # Build up a stack of contexts (created by opening file) so we can automatically close them on exit.
    with ExitStack() as stack:
        for file_name, mode in files.items():
            LOGGER.debug("Opening file %s in mode %s", file_name, mode)
            if file_name not in call_args:
                raise ValueError(f"Argument {file_name} is missing and expected to be opened in {mode} mode.")
            if isinstance(call_args[file_name], (str, pathlib.PurePath)):
                # If they open something with a `s` at the start we will shadow page it. All writes will be done to a
                # temporary version of the file which will atomically copied over the real file once closed.
                if mode.startswith("s"):
                    if "w" not in mode:
                        raise ValueError(
                            f"Shadow paging (requested by pre-pending `s` to the {call_args[file_name]}'s file mode) only supported for writing, got {mode[1:]}"
                        )
                    call_args[file_name] = stack.enter_context(
                        ShadowPage(call_args[file_name], mode[1:], encoding=None if "b" in mode else UTF_8)
                    )
                # Open the file based on the argument, record the opening in the context of things to be closed, and
                # add the opened file to the parameter name to argument value mapping
                else:
                    call_args[file_name] = stack.enter_context(
                        open(call_args[file_name], mode=mode, encoding=None if "b" in mode else UTF_8)
                    )
        yield call_args


@parameterize
def file_or_name(function: Callable, **kwargs: Dict[str, str]) -> Callable:
    """Transparently allow arguments to be either strings or open files.

    Note:
        If there are no kwargs it is assumed the first argument is a file that will be
        opened in read mode ``"r"``

    Note:
        If you need a file to be opened with extra arguments, for example ``newline=''``
        for files that will be used with the stdlib csv writer, you should manually
        open the file and pass the resulting file object in.

    Args:
        function: The user defined function that we will manager the file opening for.
        kwargs: The parameters of `function` that are considered files to be opened.
            these are interpreted in the for `name=mode` and is used to create a mapping
            of parameters whose values should be opened as file with the provided mode.
            For example if the value of the `wf` parameter to your function should be
            opened in write mode you should decorate your function with ``@file_or_name(wf='w')``

    Returns:
        A decorated function where specified arguments are interpreted as file names and opened
        automatically.
    """
    files = kwargs
    # If no file modes are specified in the kwargs we set the first argument to be opened in read mode
    if not files:
        first = get_first_parameter(function)
        LOGGER.debug("No file parameters provided, using %s='r'", first)
        files[first] = "r"
    # We need to check if we are a generator out here because if we waited to check in the
    # open_arg_files function then open_arg_files would be a generator no matter what because
    # it would have a yield in it (even if that code path wasn't executed for a function)
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
