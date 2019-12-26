import inspect
from functools import wraps
from typing import Callable, Any, List, Dict, Tuple


__all__ = ["file_or_name"]


def parameterize(function: Callable[[Any], Any]) -> Callable[[Any], Any]:
    @wraps(function)
    def wrapped(*args, **kwargs):
        if len(args) == 1 and not kwargs and callable(args[0]):
            return function(args[0])
        return lambda x: function(x, *args, **kwargs)

    return wrapped


def open_files(
    files: Dict[str, str], function: Callable[[Any], Any], *args: List[Any], **kwargs: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[str]]:
    to_close = []
    call_args = inspect.getcallargs(function, *args, **kwargs)
    for file_name, mode in files.items():
        if isinstance(call_args[file_name], str):
            call_args[file_name] = open(call_args[file_name], mode=mode, encoding=None if "b" in mode else "utf-8")
            to_close.append(file_name)
    return call_args, to_close


def get_first_parameter(function: Callable[[Any], Any]) -> str:
    sig = inspect.signature(function)
    return list(sig.parameters.keys())[0]


@parameterize
def file_or_name(function: Callable[[Any], Any], **kwargs: Dict[str, str]) -> Callable[[Any], Any]:
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
        files[get_first_parameter(function)] = "r"
    to_close = []
    # We
    if inspect.isgeneratorfunction(function):

        @wraps(function)
        def open_arg_files(*args, **kwargs):
            try:
                call_args, to_close = open_files(files, function, *args, **kwargs)
                # If the function we are calling is a generator we need to yield from it until it is
                # exhausted, if we just return the files would be closed after the first yield
                yield from function(**call_args)
            finally:
                # Make sure all the files we opened are closed
                for f in to_close:
                    call_args[f].close()

    else:

        @wraps(function)
        def open_arg_files(*args, **kwargs):
            try:
                call_args, to_close = open_files(files, function, *args, **kwargs)
                return function(**call_args)
            finally:
                for f in to_close:
                    call_args[f].close()

    return open_arg_files
