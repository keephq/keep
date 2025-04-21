import pytest

from keep.iohandler.iohandler import IOHandler, TemplateEngine, RenderException


@pytest.mark.parametrize(
    "template",
    [
        # Jinja control structures
        "{% if steps.condition %}True{% else %}False{% endif %}",
        "{% for item in steps.items %}{{ item }}{% endfor %}",
        # Filters
        "{{ steps.name | upper }}",
        # Jinja comments
        "{# This is a Jinja comment #}",
        # Variable assignment
        "{% set total = 100 %}Total: {{ total }}",
        # Jinja block structure
        "{% block content %}Some content{% endblock %}",
    ]
)
def test_jinja2_syntax_not_valid_with_mustache_engine(context_manager, template):
    """Test Jinja2 syntax is invalid when using the Mustache engine"""
    iohandler = IOHandler(
        context_manager,
        template_engine=TemplateEngine.MUSTACHE
    )

    context_manager.steps_context = {
        "name": "John",
        "condition": True,
        "items": ["one", "two"],
        "value": 20
    }

    with pytest.raises(RenderException):
        iohandler.render(template)

import pytest

@pytest.mark.parametrize(
    "template",
    [
        "{{#condition}}It's true!{{/condition}}",
        "{{^condition}}It's false!{{/condition}}",  # should be invalid in Jinja2
        "{{! This is a comment }}Hi {{name}}",
        "Value: {{{value}}}",  # unescaped value (triple-mustache)
    ]
)
def test_mustache_syntax_not_valid_with_jinja2_engine(context_manager, template):
    """Test Mustache syntax is invalid when using the Jinja2 engine"""
    iohandler = IOHandler(
        context_manager,
        template_engine=TemplateEngine.JINJA2
    )

    context_manager.steps_context = {
        "name": "John",
        "condition": True,
        "value": 20
    }

    with pytest.raises(RenderException):
        iohandler.render(template)

