"""
Test the io handler
"""
import json
import tempfile

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.iohandler.iohandler import IOHandler


def test_vanilla(context_manager):
    iohandler = IOHandler(context_manager)
    s = iohandler.render("hello world")
    assert s == "hello world"


def test_with_basic_context(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "name": "s",
    }
    context_manager.actions_context = {
        "name": "s2",
    }
    context_manager.providers_context = {
        "name": "s3",
    }
    s = iohandler.render("hello {{ steps.name }}")
    s2 = iohandler.render("hello {{ actions.name }}")
    s3 = iohandler.render("hello {{ providers.name }}")
    assert s == "hello s"
    assert s2 == "hello s2"
    assert s3 == "hello s3"


def test_with_function(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "some_list": [1, 2, 3],
    }
    context_manager.actions_context = {
        "some_string": "abcde",
    }
    context_manager.providers_context = {
        "name": "s3",
    }
    s = iohandler.render("hello keep.len({{ steps.some_list }})")
    assert s == "hello 3"


def test_with_function_2(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "some_list": [1, 2, 3],
    }
    context_manager.actions_context = {
        "some_string": "abcde",
    }
    context_manager.providers_context = {
        "name": "s3",
    }
    s = iohandler.render("hello keep.first({{ steps.some_list }})")
    s1 = iohandler.render("hello keep.len({{ actions.some_string }})")
    assert s == "hello 1"
    assert s1 == "hello 5"
