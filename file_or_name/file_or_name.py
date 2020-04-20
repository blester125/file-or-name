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
    """Open files that are arguments to this function call and close ones we opened after the call.

    :param files: A mapping of argument name to file mode. This should include all arguments that are files
    :param function: The user defined function we are opening these files for
    :param args: A list of positional args function was called with
    :param kwargs: A dict of keyword args function was called with
    :returns: A dict mapping argument names to argument values with the opened files inserted.
        function should now be called with this dict ** unpacked.
    """
    call_args = inspect.getcallargs(function, *args, **kwargs)
    with ExitStack() as stack:
        for file_name, mode in files.items():
            LOGGER.debug("Opening file %s in mode %s", file_name, mode)
            if file_name not in call_args:
                raise ValueError(f"Argument {file_name} is missing and expected to be opened in {mode} mode.")
            if isinstance(call_args[file_name], (str, pathlib.PurePath)):
                if mode.startswith("s"):
                    if "w" not in mode:
                        raise ValueError(
                            f"Shadow paging (requested by pre-pending `s` to the {call_args[file_name]}'s file mode) only supported for writing, got {mode[1:]}"
                        )
                    call_args[file_name] = stack.enter_context(
                        ShadowPage(call_args[file_name], mode[1:], encoding=None if "b" in mode else UTF_8)
                    )
                else:
                    call_args[file_name] = stack.enter_context(
                        open(call_args[file_name], mode=mode, encoding=None if "b" in mode else UTF_8)
                    )
        yield call_args


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
