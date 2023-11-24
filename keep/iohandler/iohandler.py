import ast
import copy

# TODO: fix this! It screws up the eval statement if these are not imported
import io
import logging
import re
import sys

import astunparse
import chevron
import requests

import keep.functions as keep_functions
from keep.contextmanager.contextmanager import ContextManager
from keep.step.step_provider_parameter import StepProviderParameter


class RenderException(Exception):
    pass


class IOHandler:
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        # whether Keep should shorten urls in the message or not
        # todo: have a specific parameter for this?
        self.shorten_urls = False
        if (
            self.context_manager.click_context
            and self.context_manager.click_context.params.get("api_key")
            and self.context_manager.click_context.params.get("api_url")
        ):
            self.shorten_urls = True

    def render(self, template, safe=False, default=""):
        # rendering is only support for strings
        if not isinstance(template, str):
            return template
        # check if inside the mustache is object in the context
        if template.count("}}") != template.count("{{"):
            raise Exception(
                f"Invalid template - number of }} and {{ does not match {template}"
            )
        # TODO - better validate functions
        if template.count("(") != template.count(")"):
            raise Exception(
                f"Invalid template - number of ( and ) does not match {template}"
            )
        val = self.parse(template, safe, default)
        return val

    def quote(self, template):
        """Quote {{ }} with ''

        Args:
            template (str): string with {{ }} variables in it

        Returns:
            str: string with {{ }} variables quoted with ''
        """
        pattern = r"(?<!')\{\{[\s]*([^\}]+)[\s]*\}\}(?!')"
        replacement = r"'{{ \1 }}'"
        return re.sub(pattern, replacement, template)

    def parse(self, string, safe=False, default=""):
        """Use AST module to parse 'call stack'-like string and return the result

        Example -
            string = "first(split('1 2 3', ' '))" ==> 1

        Args:
            tree (_type_): _description_

        Returns:
            _type_: _description_
        """
        # break the string to tokens
        # this will break the following string to 3 tokens:
        # string - "Number of errors: {{ steps.grep.condition.threshold.compare_to }}
        #               [threshold was set to len({{ steps.grep.condition.threshold.value }})]
        #               Error: split({{ foreach.value }},'a', 'b')
        #               and first(split({{ foreach.value }},'a', 'b'))"
        # tokens (with {{ expressions }} already rendered) -
        #           len({{ steps.grep.condition.threshold.value }})
        #           split({{ foreach.value }},'a', 'b')
        #           first(split({{ foreach.value }},'a', 'b'))

        # first render everything using chevron
        # inject the context
        string = self._render(string, safe, default)

        # Now, extract the token if exists -
        pattern = (
            r"\bkeep\.\w+\((?:[^()]*|\((?:[^()]*|\((?:[^()]*|\([^()]*\))*\))*\))*\)"
        )
        parsed_string = copy.copy(string)
        matches = re.findall(pattern, parsed_string)
        tokens = list(matches)

        if len(tokens) == 0:
            return parsed_string
        elif len(tokens) == 1:
            token = "".join(tokens[0])
            val = self._parse_token(token)
            parsed_string = parsed_string.replace(token, str(val))
            return parsed_string
        # this basically for complex expressions with functions and operators
        for token in tokens:
            token = "".join(token)
            val = self._parse_token(token)
            parsed_string = parsed_string.replace(token, str(val))

        return parsed_string

    def _parse_token(self, token):
        # else, it contains a function e.g. len({{ value }}) or split({{ value }}, 'a', 'b')
        def _parse(self, tree):
            if isinstance(tree, ast.Module):
                return _parse(self, tree.body[0].value)

            if isinstance(tree, ast.Call):
                func = tree.func
                args = tree.args
                # if its another function
                _args = []
                for arg in args:
                    _arg = None
                    if isinstance(arg, ast.Call):
                        _arg = _parse(self, arg)
                    elif isinstance(arg, ast.Str) or isinstance(arg, ast.Constant):
                        _arg = arg.s
                    # set is basically {{ value }}
                    elif isinstance(arg, ast.Set) or isinstance(arg, ast.List):
                        _arg = astunparse.unparse(arg).strip()
                        if (
                            (_arg.startswith("[") and _arg.endswith("]"))
                            or (_arg.startswith("{") and _arg.endswith("}"))
                            or (_arg.startswith("(") and _arg.endswith(")"))
                        ):
                            try:
                                # TODO(shahargl): when Keep gonna be self hosted, this will be a security issue!!!
                                # because the user can run any python code need to find a way to limit the functions that can be used

                                # https://github.com/keephq/keep/issues/138
                                from dateutil.tz import tzutc

                                g = globals()
                                # we need to pass the classes of the dependencies to the eval
                                for dependency in self.context_manager.dependencies:
                                    g[dependency.__name__] = dependency

                                # TODO: this is a hack to tzutc in the eval, should be more robust
                                g["tzutc"] = tzutc
                                # finally, eval the expression
                                _arg = eval(_arg, g)
                            except ValueError:
                                pass
                    else:
                        _arg = arg.id
                    if _arg:
                        _args.append(_arg)
                val = getattr(keep_functions, func.attr)(*_args)
                return val

        try:
            tree = ast.parse(token)
        except SyntaxError as e:
            if "unterminated string literal" in str(e):
                # try to HTML escape the string
                # this is happens when libraries such as datadog api client
                # HTML escapes the string and then ast.parse fails ()
                # https://github.com/keephq/keep/issues/137
                import html

                tree = ast.parse(html.unescape(token))
            else:
                # for strings such as "45%\n", we need to escape
                tree = ast.parse(token.encode("unicode_escape"))
        return _parse(self, tree)

    def _render(self, key, safe=False, default=""):
        # change [] to . for the key because thats what chevron uses
        _key = key.replace("[", ".").replace("]", "")

        context = self.context_manager.get_full_context()
        # TODO: protect from multithreaded where another thread will print to stderr, but thats a very rare case and we shouldn't care much
        original_stderr = sys.stderr
        sys.stderr = io.StringIO()
        rendered = chevron.render(_key, context, warn=True)
        stderr_output = sys.stderr.getvalue()
        sys.stderr = original_stderr
        # If render should failed if value does not exists
        if safe and "Could not find key" in stderr_output:
            raise RenderException(
                f"Could not find key {key} in context - {stderr_output}"
            )
        if not rendered:
            return default
        return rendered

    def render_context(self, context_to_render: dict):
        """
        Iterates the provider context and renders it using the workflow context.
        """
        # Don't modify the original context
        context_to_render = copy.deepcopy(context_to_render)
        for key, value in context_to_render.items():
            if isinstance(value, str):
                context_to_render[key] = self._render_template_with_context(
                    value, safe=True
                )
            elif isinstance(value, list):
                context_to_render[key] = self._render_list_context(value)
            elif isinstance(value, dict):
                context_to_render[key] = self.render_context(value)
            elif isinstance(value, StepProviderParameter):
                safe = value.safe and value.default is not None
                context_to_render[key] = self._render_template_with_context(
                    value.key, safe=safe, default=value.default
                )
        return context_to_render

    def _render_list_context(self, context_to_render: list):
        """
        Iterates the provider context and renders it using the workflow context.
        """
        for i in range(0, len(context_to_render)):
            value = context_to_render[i]
            if isinstance(value, str):
                context_to_render[i] = self._render_template_with_context(
                    value, safe=True
                )
            if isinstance(value, list):
                context_to_render[i] = self._render_list_context(value)
            if isinstance(value, dict):
                context_to_render[i] = self.render_context(value)
        return context_to_render

    def _render_template_with_context(
        self, template: str, safe: bool = False, default: str = ""
    ) -> str:
        """
        Renders a template with the given context.

        Args:
            template (str): template (string) to render

        Returns:
            str: rendered template
        """
        rendered_template = self.render(template, safe, default)

        # shorten urls if enabled
        if self.shorten_urls:
            rendered_template = self.__patch_urls(rendered_template)

        return rendered_template

    def __patch_urls(self, rendered_template: str) -> str:
        """
        shorten URLs found in the message.

        Args:
            rendered_template (str): The rendered template that might contain URLs
        """
        urls = re.findall(
            r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+/?.*", rendered_template
        )
        # didn't find any url
        if not urls:
            return rendered_template

        shortened_urls = self.__get_short_urls(urls)
        for url, shortened_url in shortened_urls.items():
            rendered_template = rendered_template.replace(url, shortened_url)
        return rendered_template

    def __get_short_urls(self, urls: list) -> dict:
        """
        Shorten URLs using Keep API.

        Args:
            urls (list): list of urls to shorten

        Returns:
            dict: a dictionary containing the original url as key and the shortened url as value
        """
        try:
            api_url = self.context_manager.click_context.params.get("api_url")
            api_key = self.context_manager.click_context.params.get("api_key")
            response = requests.post(
                f"{api_url}/s", json=urls, headers={"x-api-key": api_key}
            )
            if response.ok:
                return response.json()
            else:
                self.logger.error(
                    "Failed to request short URLs from API",
                    extra={
                        "response": response.text,
                        "status_code": response.status_code,
                    },
                )
        except Exception:
            self.logger.exception("Failed to request short URLs from API")
