import ast
import copy
import html

# TODO: fix this! It screws up the eval statement if these are not imported
import inspect
import io
import json
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
    def __init__(self, message, missing_keys=None):
        self.missing_keys = missing_keys
        super().__init__(message)


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

    def render(self, template, safe=False, default="", additional_context=None):
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
        val = self.parse(template, safe, default, additional_context)
        return val

    def quote(self, template):
        """Quote {{ }} with ""

        Args:
            template (str): string with {{ }} variables in it

        Returns:
            str: string with {{ }} variables quoted with ""
        """
        pattern = r"(?<!')\{\{[\s]*([^\}]+)[\s]*\}\}(?!')"
        replacement = r'"{{ \1 }}"'
        return re.sub(pattern, replacement, template)

    def extract_keep_functions(self, text):
        matches = []
        i = 0
        while i < len(text):
            if text[i : i + 5] == "keep.":
                start = i
                func_start = text.find("(", start)
                if func_start > -1:  # Opening '(' found after "keep."
                    i = func_start + 1  # Move i to the character after '('
                    parent_count = 1
                    in_string = False
                    escape_next = False
                    quote_char = ""
                    escapes = {}
                    while i < len(text) and (parent_count > 0 or in_string):
                        if text[i] == "\\" and in_string and not escape_next:
                            escape_next = True
                            i += 1
                            continue
                        elif text[i] in ('"', "'"):
                            if not in_string:
                                # Detecting the beginning of the string
                                in_string = True
                                quote_char = text[i]
                            elif (
                                text[i] == quote_char
                                and not escape_next
                                and (
                                    str(text[i + 1]).isalnum() == False
                                    and str(text[i + 1]) != " "
                                )  # end of statement, arg, etc. if its alpha numeric or whitespace, we just need to escape it
                            ):
                                # Detecting the end of the string
                                # If the next character is not alphanumeric or whitespace, it's the end of the string
                                in_string = False
                                quote_char = ""
                            elif text[i] == quote_char and not escape_next:
                                escapes[i] = text[
                                    i
                                ]  # Save the quote character where we need to escape for valid ast parsing
                        elif text[i] == "(" and not in_string:
                            parent_count += 1
                        elif text[i] == ")" and not in_string:
                            parent_count -= 1

                        escape_next = False
                        i += 1

                    if parent_count == 0:
                        matches.append((text[start:i], escapes))
                    continue  # Skip the increment at the end of the loop to continue from the current position
                else:
                    # If no '(' found, increment i to move past "keep."
                    i += 5
            else:
                i += 1
        return matches

    def _trim_token_error(self, token):
        # trim too long tokens so that the error message will be readable
        if len(token) > 64:
            try:
                func_name = token.split("keep.")[1].split("(")[0]
                err = f"keep.{func_name}(...)"
            except Exception:
                err = token
            finally:
                return err
        else:
            return token

    def parse(self, string, safe=False, default="", additional_context=None):
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
        string = self._render(string, safe, default, additional_context)

        # Now, extract the token if exists
        parsed_string = copy.copy(string)

        if string.startswith("raw_render_without_execution(") and string.endswith(")"):
            tokens = []
            string = string.replace("raw_render_without_execution(", "", 1)
            string = string[::-1].replace(")", "", 1)[::-1]  # Remove the last ')'
            parsed_string = copy.copy(string)
        else:
            tokens = self.extract_keep_functions(parsed_string)

        if len(tokens) == 0:
            return parsed_string
        elif len(tokens) == 1:
            token, escapes = tokens[0]
            token_to_replace = token
            try:
                escapes_counter = 0
                if escapes:
                    for escape in escapes:
                        token = (
                            token[: escape + escapes_counter]
                            + "\\"
                            + token[escape + escapes_counter :]
                        )
                        escapes_counter += 1  # we need to increment the counter because we added a character
                val = self._parse_token(token)
            except Exception as e:
                # trim stacktrace since we have limitation on the error message
                trimmed_token = self._trim_token_error(token)
                err_message = str(e).splitlines()[-1]
                raise Exception(
                    f"Got {e.__class__.__name__} while parsing token '{trimmed_token}': {err_message}"
                )
            # support JSON
            if isinstance(val, dict):
                # if the value we need to replace is the whole string,
                #  and its a dict, just return the dict
                # the usage is for
                #   with:
                #   method: POST
                #   body:
                #     alert: keep.json_loads('{{ alert }}')
                if parsed_string == token_to_replace:
                    return val
                else:
                    val = json.dumps(val)
            else:
                val = str(val)
            parsed_string = parsed_string.replace(token_to_replace, val)
            return parsed_string
        # this basically for complex expressions with functions and operators
        tokens_handled = set()
        for token in tokens:
            token, escapes = token
            # imagine " keep.f(..) > 1 and keep.f(..) <2"
            # so keep.f already handled, we don't want to handle it again
            if token in tokens_handled:
                continue
            token_to_replace = token
            try:
                if escapes:
                    for escape in escapes:
                        token = token[:escape] + "\\" + token[escape:]
                val = self._parse_token(token)

            except Exception as e:
                trimmed_token = self._trim_token_error(token)
                err_message = str(e).splitlines()[-1]
                raise Exception(
                    f"Got {e.__class__.__name__} while parsing token '{trimmed_token}': {err_message}"
                )
            parsed_string = parsed_string.replace(token_to_replace, str(val))
            tokens_handled.add(token_to_replace)

        return parsed_string

    def _parse_token(self, token):
        # else, it contains a function e.g. len({{ value }}) or split({{ value }}, 'a', 'b')
        def _parse(self, tree):
            if isinstance(tree, ast.Module):
                return _parse(self, tree.body[0].value)

            if isinstance(tree, ast.Call):
                func = tree.func
                args = tree.args
                keywords = tree.keywords  # Get keyword arguments

                # Parse positional args
                _args = []
                for arg in args:
                    _arg = None
                    if isinstance(arg, ast.Call):
                        _arg = _parse(self, arg)
                    elif isinstance(arg, ast.Str) or isinstance(arg, ast.Constant):
                        _arg = str(arg.s)
                    elif isinstance(arg, ast.Dict):
                        _arg = ast.literal_eval(arg)
                    elif (
                        isinstance(arg, ast.Set)
                        or isinstance(arg, ast.List)
                        or isinstance(arg, ast.Tuple)
                    ):
                        _arg = astunparse.unparse(arg).strip()
                        if (
                            (_arg.startswith("[") and _arg.endswith("]"))
                            or (_arg.startswith("{") and _arg.endswith("}"))
                            or (_arg.startswith("(") and _arg.endswith(")"))
                        ):
                            try:
                                import datetime

                                from dateutil.tz import tzutc

                                g = globals()
                                # we need to pass the classes of the dependencies to the eval
                                for dependency in self.context_manager.dependencies:
                                    g[dependency.__name__] = dependency

                                g["tzutc"] = tzutc
                                g["datetime"] = datetime
                                _arg = eval(_arg, g)
                            except ValueError:
                                pass
                    else:
                        _arg = arg.id
                    # if the value is empty '', we still need to pass it to the function
                    if _arg or _arg == "":
                        _args.append(_arg)

                # Parse keyword args
                _kwargs = {}
                for keyword in keywords:
                    key = keyword.arg
                    value = keyword.value

                    if isinstance(value, ast.Call):
                        _kwargs[key] = _parse(self, value)
                    elif isinstance(value, ast.Str) or isinstance(value, ast.Constant):
                        _kwargs[key] = str(value.s)
                    elif isinstance(value, ast.Dict):
                        _kwargs[key] = ast.literal_eval(value)
                    elif (
                        isinstance(value, ast.Set)
                        or isinstance(value, ast.List)
                        or isinstance(value, ast.Tuple)
                    ):
                        parsed_value = astunparse.unparse(value).strip()
                        if (
                            (
                                parsed_value.startswith("[")
                                and parsed_value.endswith("]")
                            )
                            or (
                                parsed_value.startswith("{")
                                and parsed_value.endswith("}")
                            )
                            or (
                                parsed_value.startswith("(")
                                and parsed_value.endswith(")")
                            )
                        ):
                            try:
                                import datetime

                                from dateutil.tz import tzutc

                                g = globals()
                                for dependency in self.context_manager.dependencies:
                                    g[dependency.__name__] = dependency

                                g["tzutc"] = tzutc
                                g["datetime"] = datetime
                                _kwargs[key] = eval(parsed_value, g)
                            except ValueError:
                                pass
                    else:
                        _kwargs[key] = value.id

                # Get the function and its signature
                keep_func = getattr(keep_functions, func.attr)
                func_signature = inspect.signature(keep_func)

                # Add tenant_id if needed
                if "kwargs" in func_signature.parameters:
                    _kwargs["tenant_id"] = self.context_manager.tenant_id

                try:
                    # Call function with both positional and keyword arguments
                    val = keep_func(*_args, **_kwargs)
                except ValueError:
                    # Handle newline escaping if needed
                    _args = [
                        arg.replace("\n", "\\n") if isinstance(arg, str) else arg
                        for arg in _args
                    ]
                    _kwargs = {
                        k: v.replace("\n", "\\n") if isinstance(v, str) else v
                        for k, v in _kwargs.items()
                    }
                    val = keep_func(*_args, **_kwargs)

                return val

        try:
            tree = ast.parse(token)
        except SyntaxError as e:
            if "unterminated string literal" in str(e):
                # try to HTML escape the string
                # this is happens when libraries such as datadog api client
                # HTML escapes the string and then ast.parse fails ()
                # https://github.com/keephq/keep/issues/137
                try:
                    unescaped_token = html.unescape(
                        token.replace("\r\n", "").replace("\n", "")
                    )
                    tree = ast.parse(unescaped_token)
                # try best effort to parse the string
                # this is some nasty bug. see test test_openobserve_rows_bug on test_iohandler
                # and this ticket -
                except Exception as e:
                    # for strings such as "45%\n", we need to escape
                    t = (
                        html.unescape(token.replace("\r\n", "").replace("\n", ""))
                        .replace("\\n", "\n")
                        .replace("\\", "")
                        .replace("\n", "\\n")
                    )
                    t = self._encode_single_quotes_in_double_quotes(t)
                    try:
                        tree = ast.parse(t)
                    except Exception:
                        # For strings where ' is used as the delimeter and we failed to escape all ' in the string
                        # @tb: again, this is not ideal but it's best effort...
                        t = (
                            t.replace("('", '("')
                            .replace("')", '")')
                            .replace("',", '",')
                        )
                        tree = ast.parse(t)
            else:
                # for strings such as "45%\n", we need to escape
                tree = ast.parse(token.encode("unicode_escape"))
        return _parse(self, tree)

    def _render(self, key: str, safe=False, default="", additional_context=None):
        if "{{^" in key or "{{ ^" in key:
            self.logger.debug(
                "Safe render is not supported when there are inverted sections."
            )
            safe = False

        context = self.context_manager.get_full_context(exclude_providers=True)

        if additional_context:
            context.update(additional_context)

        # TODO: protect from multithreaded where another thread will print to stderr, but thats a very rare case and we shouldn't care much
        original_stderr = sys.stderr
        sys.stderr = io.StringIO()
        rendered = self.render_recursively(key, context)
        # chevron.render will escape the quotes, we need to unescape them
        rendered = rendered.replace("&quot;", '"')
        stderr_output = sys.stderr.getvalue()
        sys.stderr = original_stderr
        # If render should failed if value does not exists
        if safe and "Could not find key" in stderr_output:
            # if more than one keys missing, pretiffy the error
            if stderr_output.count("Could not find key") > 1:
                missing_keys = stderr_output.split("Could not find key")
                missing_keys = [
                    missing_key.strip().replace("\n", "")
                    for missing_key in missing_keys[1:]
                ]
                missing_keys = list(set(missing_keys))
                err = "Could not find keys: " + ", ".join(missing_keys)
            else:
                missing_keys = [stderr_output.split("Could not find key")[1].strip()]
                err = stderr_output.replace("\n", "")
            raise RenderException(f"{err} in the context.", missing_keys=missing_keys)
        if not rendered:
            return default

        return rendered

    def _encode_single_quotes_in_double_quotes(self, s):
        result = []
        in_double_quotes = False
        i = 0
        while i < len(s):
            if s[i] == '"':
                in_double_quotes = not in_double_quotes
            elif s[i] == "'" and in_double_quotes:
                if i > 0 and s[i - 1] == "\\":
                    # If the single quote is already escaped, don't add another backslash
                    result.append(s[i])
                else:
                    result.append("\\" + s[i])
                i += 1
                continue
            result.append(s[i])
            i += 1
        return "".join(result)

    def render_context(self, context_to_render: dict, additional_context: dict = None):
        """
        Iterates the provider context and renders it using the workflow context.
        """
        # Don't modify the original context
        context_to_render = copy.deepcopy(context_to_render)
        for key, value in context_to_render.items():
            if isinstance(value, str):
                context_to_render[key] = self._render_template_with_context(
                    value, safe=True, additional_context=additional_context
                )
            elif isinstance(value, list):
                context_to_render[key] = self._render_list_context(
                    value, additional_context=additional_context
                )
            elif isinstance(value, dict):
                context_to_render[key] = self.render_context(
                    value, additional_context=additional_context
                )
            elif isinstance(value, StepProviderParameter):
                safe = value.safe and value.default is not None
                context_to_render[key] = self._render_template_with_context(
                    value.key,
                    safe=safe,
                    default=value.default,
                    additional_context=additional_context,
                )
        return context_to_render

    def _render_list_context(
        self, context_to_render: list, additional_context: dict = None
    ):
        """
        Iterates the provider context and renders it using the workflow context.
        """
        for i in range(0, len(context_to_render)):
            value = context_to_render[i]
            if isinstance(value, str):
                context_to_render[i] = self._render_template_with_context(
                    value, safe=True, additional_context=additional_context
                )
            if isinstance(value, list):
                context_to_render[i] = self._render_list_context(
                    value, additional_context=additional_context
                )
            if isinstance(value, dict):
                context_to_render[i] = self.render_context(
                    value, additional_context=additional_context
                )
        return context_to_render

    def _render_template_with_context(
        self,
        template: str,
        safe: bool = False,
        default: str = "",
        additional_context: dict = None,
    ) -> str:
        """
        Renders a template with the given context.

        Args:
            template (str): template (string) to render

        Returns:
            str: rendered template
        """
        rendered_template = self.render(
            template, safe, default, additional_context=additional_context
        )

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

    def render_recursively(
        self, template: str, context: dict, max_iterations: int = 10
    ) -> str:
        """
        Recursively render a template until there are no more mustache tags or max iterations reached.

        Args:
            template: The template string containing mustache tags
            context: The context dictionary for rendering
            max_iterations: Maximum number of rendering iterations to prevent infinite loops

        Returns:
            The fully rendered string
        """
        current = template
        iterations = 0

        while iterations < max_iterations:
            rendered = chevron.render(
                current, context, warn=True if iterations == 0 else False
            )

            # https://github.com/keephq/keep/issues/2326
            rendered = html.unescape(rendered)

            # If no more changes or no more mustache tags, we're done
            # we don't want to render providers. ever, so this is a hack for it for now
            if rendered == current or "{{" not in rendered or "providers." in rendered:
                return rendered

            current = rendered
            iterations += 1

        # Return the last rendered version even if we hit max iterations
        return current


if __name__ == "__main__":
    # debug & test
    context_manager = ContextManager("keep")
    context_manager.event_context = {
        "header": "HTTP API Error {{ alert.labels.statusCode }}",
        "labels": {"statusCode": "404"},
    }
    iohandler = IOHandler(context_manager)
    res = iohandler.render("{{ alert.header }}")
    from asteval import Interpreter

    aeval = Interpreter()
    evaluated_if_met = aeval(res)
    print(evaluated_if_met)
