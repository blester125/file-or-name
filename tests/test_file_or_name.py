import os
import random
import string
from typing import Optional
from itertools import chain
from unittest.mock import patch, MagicMock, call
import pytest
from file_or_name.file_or_name import get_first_parameter, file_or_name, open_files

TEST_DATA = os.path.join(os.path.realpath(os.path.dirname(__file__)), "test_data")

ONE_FILE = os.path.join(TEST_DATA, "one.txt")
ONE_VALUES = ["a", "b b", "c c c", "d d d d", "e e e e e"]

TWO_FILE = os.path.join(TEST_DATA, "two.txt")
TWO_VALUES = ["1", "2 2", "3 3 3", "4 4 4 4", "5 5 5 5 5"]


def random_string(length: Optional[int] = None, min_: int = 3, max_: int = 5) -> str:
    length = random.randint(min_, max_) if length is None else length
    return "".join(random.choice(string.ascii_lowercase) for _ in range(length))


@pytest.fixture
def write_file():
    file_name = os.path.join(TEST_DATA, random_string())
    yield file_name
    try:
        os.remove(file_name)
    except:
        pass


def read(f):
    return [l.rstrip() for l in f]


def read_gen(f):
    yield from (l.rstrip() for l in f)


def write(wf, msg):
    return wf.write(msg)


def write_gen(wf, msg):
    yield wf.write(msg)


def read_two(f, f2):
    return list(l.rstrip() for l in chain(f, f2))


def read_two_gen(f, f2):
    yield from (l.rstrip() for l in chain(f, f2))


def string_plus_file(s, f):
    return list(chain([s], (l.rstrip() for l in f)))


def test_first_param_positional():
    def func(a, b):
        pass

    first_param = get_first_parameter(func)
    assert first_param == "a"


def test_first_param_with_default():
    def func(a=12):
        pass

    first_param = get_first_parameter(func)
    assert first_param == "a"


def test_first_param_keyword_only():
    def func(*, a):
        pass

    first_param = get_first_parameter(func)
    assert first_param == "a"


def test_first_param_keyword_only_with_default():
    def func(*, a=12):
        pass

    first_param = get_first_parameter(func)
    assert first_param == "a"


def test_file_or_name_default_to_first():
    r = file_or_name(read)
    data = r(ONE_FILE)
    assert data == ONE_VALUES

    data = r(TWO_FILE)
    assert data == TWO_VALUES


def test_file_or_name_gen_default_to_first():
    r = file_or_name(read_gen)
    data = [x for x in r(ONE_FILE)]
    assert data == ONE_VALUES

    data = [x for x in r(TWO_FILE)]
    assert data == TWO_VALUES


def test_file_or_name_write_mode(write_file):
    w = file_or_name(wf="w")(write)
    data = "\n".join(random_string() for _ in range(random.randint(1, 10)))
    w(write_file, data)
    with open(write_file) as f:
        res = f.read()
    assert res == data


def test_file_or_name_gen_write_mode(write_file):
    w = file_or_name(wf="w")(write_gen)
    data = "\n".join(random_string() for _ in range(random.randint(1, 10)))
    list(w(write_file, data))
    with open(write_file) as f:
        res = f.read()
    assert res == data


def test_file_or_name_read_two():
    r = file_or_name(f="r", f2="r")(read_two)
    data = r(ONE_FILE, TWO_FILE)
    assert data == ONE_VALUES + TWO_VALUES


def test_file_or_name_read_two_gen():
    r = file_or_name(f="r", f2="r")(read_two_gen)
    data = list(r(ONE_FILE, TWO_FILE))
    assert data == ONE_VALUES + TWO_VALUES


def test_file_or_name_skips_first_if_other_specified():
    r = file_or_name(f="r")(string_plus_file)
    string = random_string()
    data = r(string, ONE_FILE)
    assert data == [string] + ONE_VALUES


def test_open_files_error_on_missing_argument():
    with patch("file_or_name.file_or_name_module.inspect.getcallargs") as call_patch:
        files = {"missing": "r"}
        call_patch.return_value = {}
        with pytest.raises(ValueError):
            with open_files(files, lambda x: x) as f:
                pass


def test_open_files_opens_and_closes_files():
    gold = [
        {"parameter": random_string(), "mode": random.choice(["r", "w", "rb", "wb"])}
        for _ in range(random.randint(1, 10))
    ]
    for g in gold:
        g["encoding"] = "utf-8" if g["mode"] in {"r", "w"} else None
        if random.random() > 0.5:
            g["value"] = MagicMock()
            g["string"] = False
        else:
            g["value"] = MagicMock(spec=str)
            g["string"] = True
    files = {g["parameter"]: g["mode"] for g in gold}
    args = {g["parameter"]: g["value"] for g in gold}
    mocks = {g["value"]: MagicMock() if g["string"] else g["value"] for g in gold}
    with patch("file_or_name.file_or_name_module.inspect.getcallargs") as call_patch, patch(
        "file_or_name.file_or_name_module.open"
    ) as open_patch:
        call_patch.return_value = args
        open_patch.side_effect = lambda *args, **kwargs: mocks[args[0]]
        with open_files(files, lambda x: x):
            for g in gold:
                args = call(g["value"], mode=g["mode"], encoding=g["encoding"])
                if g["string"]:
                    assert args in open_patch.call_args_list
                else:
                    assert args not in open_patch.call_args_list
        for g in gold:
            if not g["string"]:
                mocks[g["value"]].close.assert_not_called()


@file_or_name(wf="sw")
def writing_test(wf, data, die=False):
    if die:
        raise ValueError
    wf.write(data)


@pytest.fixture
def data():
    file_name = random_string()
    gold_data = random_string()
    og_data = random_string()
    with open(file_name, "w") as wf:
        wf.write(og_data)
    yield file_name, gold_data, og_data
    os.remove(file_name)


def test_shadow_page_atomic(data):
    file_name, gold_data, og_data = data
    try:
        writing_test(file_name, gold_data, die=True)
    except ValueError:
        pass
    with open(file_name) as f:
        res = f.read()
    assert res == og_data


def test_shadow_page_write(data):
    file_name, gold_data, og_data = data
    writing_test(file_name, gold_data, die=False)
    with open(file_name) as f:
        res = f.read()
    assert res == gold_data


def test_shadow_page_on_reads(data):
    @file_or_name(f="sr")
    def test(f):
        pass

    with pytest.raises(ValueError):
        test("aaa")
