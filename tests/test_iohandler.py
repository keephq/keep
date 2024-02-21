"""
Test the io handler
"""


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
    context_manager.providers_context = {
        "name": "s2",
    }
    s = iohandler.render("hello {{ steps.name }}")
    s2 = iohandler.render("hello {{ providers.name }}")
    assert s == "hello s"
    assert s2 == "hello s2"


def test_with_function(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "some_list": [1, 2, 3],
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
    context_manager.providers_context = {
        "name": "s3",
    }
    s = iohandler.render("hello keep.first({{ steps.some_list }})")
    assert s == "hello 1"


def test_with_json_dumps(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "some_list": [1, 2, 3],
    }
    context_manager.providers_context = {
        "name": "s3",
    }
    s = iohandler.render("hello keep.json_dumps({{ steps.some_list }})")
    assert s == "hello [\n    1,\n    2,\n    3\n]"


def test_with_json_dumps_when_json_string(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "some_list": "[1, 2, 3]",
    }
    context_manager.providers_context = {
        "name": "s3",
    }
    s = iohandler.render("hello keep.json_dumps({{ steps.some_list }})")
    assert s == "hello [\n    1,\n    2,\n    3\n]"
