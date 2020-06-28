------------
File Or Name
------------


.. image:: https://img.shields.io/pypi/v/file-or-name
     :target: https://pypi.org/project/file-or-name/
     :alt: PyPI Version

.. image:: https://github.com/blester125/file-or-name/workflows/Unit%20Test/badge.svg
     :target: https://github.com/blester125/file-or-name/actions
     :alt: Actions Status

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
     :target: https://github.com/psf/black
     :alt: Code style: black

.. image:: https://readthedocs.org/projects/file-or-name/badge/?version=latest
    :target: https://file-or-name.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

Transparently handle input parameters that are either strings or pre-opened file objects.

.. contents::
   :local:
   :depth: 2

Why?
====

when writing a function that reads or writes data to a file you often end up with something that looks like this

.. code:: python

    def read_my_cool_file(file_name):
        with open(file_name) as f:
            # Process file object f
            ...

This has some problems.

 1. It couples your data processing code and the opening of the file. This makes it harder to test. The thing you are
    actually testing is the code that processes the but with code like this you need to cooridnate the opening of the
    file during the test too. You need to either create fake data on dist of patch the open call.
 2. It can't handle special files. If you have file in your special format but it uses ``latin-1`` encoding instead of
    ``ascii`` how can you use that file? You can't. The opening of the file is sealed inside the function meaning the
    user can't easily change the behavior. Practices like this force file interaction to only be done in one way.

For maximum flexibility and easy testability you probably want a function that looks like this

.. code:: python

    def read_my_cool_file(f):
        # Process file object f
        ...

This is nice because when testing you can use things like the ``io.StringIO`` objects to dynamically create test data.
You can also open files with different encodings and pass them in to get processed just like normal. This is akin to
dependency injection scheme where the creation of the thing to be processed in done outside of the process it self to
allow for swapping the exact format of the object. There is a usability draw back though. This way of processing files
is onerous on the user. It turns single function calls into multi-line calls. This

.. code:: python

    data = read_my_cool_file("/path/to/my/imporant/data")

becomes this

.. code:: python

    with open("/path/to/my/important/data") as f:
        data = read_my_cool_file(f)

Functions like this are also a divergence from a lot of other functions a user probably uses. Forcing the user to do
things differently for your library is a sure fire way to reduce adoption.

We need a way to accept both file paths (as strings) and file objects without having to write code to check which it is
for every io function we write.

What?
=====

Enter ``file_or_name``.

``file_or_name`` introduces a decorator ``@file_or_name`` that solves this issue for us.

By decorating a function with ``@file_or_name`` we can accept both strings and file objects. Our example above becomes

.. code:: python

    @file_or_name
    def read_my_cool_file(f):
        # Process file object f
        ...

As the writer of the function we can write functions that assume they always get a file object as input. This means we
can stop opening files inside functions which makes them easier to test.

As a user we can pass in either a path to a file (as a string) making the function easy to call, or we can pass in an
open file object which lets us control exactly how the is opened (control encoding and whatnot).


Usage
=====

The ``@file_or_name`` decorator will automatically open and close files when specified parameters have strings as their
argument value. If you use the decorator with no arguments it will open the first argument as a file in read mode.

.. code:: python

    from file_or_name import file_or_name

    @file_or_name
    def read_json(f):
        return json.load(f)

In order to handle multiple files and file writing we can pass keyword arguments to the decorator in the form
``parameter=mode``. This will open a file specified by the argument value for ``parameter`` using mode specified by this
keyword argument.

Writing to file example, when the ``wf`` argument is a string it will automatically be opened in write mode:

.. code:: python

    from file_or_name import file_or_name

    @file_or_name(wf='w')
    def write_json(data, wf):
        json.dumps(data, wf, indent=2)

Reading and writing example, any argument values that are strings for either ``rf`` or ``wf`` will be opened in read
mode and write mode respectivly:

.. code:: python

    from file_or_name import file_or_name

    @file_or_name(rf='r', wf='w')
    def convert_jsonl_to_yaml(rf, wf):
        for line in rf:
            wf.write(yaml.dump(json.loads(line)) + "\n")

File or Name lets you, the library developer, write function that operate on files object making code cleaner and more
testable while letting your users interact with your code using simple file path string arguments. It also will
automatically open pathlib objects as arguments too.


Shadow Paging
=============

I often have code that will read from a file with a generator, this lets me process chunks of data at a time and I don't
have to worry about materializing the whole file in memory. The problem is when I want to read data from a file, make
changes  to it and then write back to that same file. You can't open that file for writing because that would destroy
the data you are lazily reading from it with the generator. A common solution is to read the data in and keep it in
memory, process the data and write it all back. This defeats the purpose of using a generator in the first place, it
also means it is possible to have a error when writing data that will leave you in a state were your data disappeared.
This is why I introduced the shadow page to this library. Using a ``NamedTemporaryFile`` you can write to this file as
much as you want and when you close the file it will be automatically used to replace the file on disk in an atomic way,
This means you can't lose you data by having a bug during writing and it lets you write back to a file that you are
using a generator to read from.

You can use this functionality by prefixing your write modes with a ``s``


.. code:: python

    from file_or_name import file_or_name

    @file_or_name(f='r', wf='sw')
    def reverse(f, wf):
        data = f.read()[::-1]
        if random.random() < 0.5:
            raise ValueError
        wf.write(data)

Without a shadow page when you read in this data and try to write it the possibility of a the ``ValueError`` between
when the file is opened for writing and when it is actually written could cause you to lose all your data. If the error
occurs when using the shadow page your original read data will be left intact and if the error doesn't happen then the
data will be reversed.
