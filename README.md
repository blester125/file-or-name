# File Or Name

[![PyPi Version](https://img.shields.io/pypi/v/file-or-name)](https://pypi.org/project/file-or-name/) [![Actions Status](https://github.com/blester125/file-or-name/workflows/Unit%20Test/badge.svg)](https://github.com/blester125/file-or-name/actions) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Transparently handle input parameters that are either strings or pre-opened file objects.

## Why?

when writing a function that reads or writes data to a file you often end up with something that looks like this

```python
def read_my_cool_file(file_name):
    with open(file_name) as f:
        # Process file object f
        ...
```

This has some problems.

 1. It couples your data processing code and the opening of the file. This makes it
    harder to test. You only want to test your code that processes the data but with functions like this
    you need to coordinate the opening of the file during you test, either creating fake data on disk or
    patching the open call.
 2. It can't handle special files. If you have file in your special format but it uses `latin-1` encoding
    instead of `ascii` how can you use that file? You can't because you are opening the file in function
    instead of passing the file object in you are forced to open it in one way.

For maximum flexibility and easy testability you probably actually want a function that looks like this

```python
def read_my_cool_file(f):
    # Process file object f
    ...
```

This is nice because when testing you can use things like the `io.StringIO` objects to dynamically create test
data. You can also open files with different encodings and pass them in to get processed just like normal. There
is a usability draw back though. This way of processing files is onerous on the user. It turns single function
calls into multi-line calls. This

```python
data = read_my_cool_file("/path/to/my/imporant/data")
```

into this

```python
with open("/path/to/my/important/data") as f:
    data = read_my_cool_file(f)
```

It also is a divergence from a lot of other functions they probably use, forcing the user to do things differently for
your library is hard for them and could result in them not using your code.

We need a way to accept both file paths (as strings) and file objects without having to write code to check which it is
for every io function we write.


## What?

Enter `file_or_name`.

`file_or_name` introduces a decorator `file_or_name` that solves this issue.

By decorating a function with `@file_or_name` we can accept both strings and file objects. Our example above becomes

```python
@file_or_name
def read_my_cool_file(f):
    # Process file object f
    ...
```

As writer of the function we can write functions that assume they get a file object and input. This means we can stop
opening files as functions it makes it easier to test.

As a user we can pass in either a string making the function easy to call or we can pass in a file object which lets us
handle files with other encodings.


## Usage

The `@file_or_name` decorator will open and close files automatically for you when your function takes a file. If you
use the decorator with no arguments it will open the first argument as a file in read mode.

In order to handle multiple files as well as writing use keyword arguments to the decorator in the form `parameter=mode`.
This will open a file using the value of parameter as a file in the specified mode.

Writing to file example:

```python
@file_or_name(wf='w')
def write_json(data, wf):
    json.dumps(data, wf, indent=2)
```

Reading and writing example:

```python
@file_or_name(rf='r', wf='w')
def convert_jsonl_to_yaml(rf, wf):
    for line in rf:
        wf.write(yaml.dump(json.loads(line)) + "\n")
```

File or Name lets you the library develop write function that operate on files object making code cleaner and more
testable while letting your users interact with your code using simple file path string arguments.
