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
        parsed_string = copy.copy(string)
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
                # if its another function
                _args = []
                for arg in args:
                    _arg = None
                    if isinstance(arg, ast.Call):
                        _arg = _parse(self, arg)
                    elif isinstance(arg, ast.Str) or isinstance(arg, ast.Constant):
                        _arg = str(arg.s)
                    elif isinstance(arg, ast.Dict):
                        _arg = ast.literal_eval(arg)
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
                                import datetime

                                from dateutil.tz import tzutc

                                g = globals()
                                # we need to pass the classes of the dependencies to the eval
                                for dependency in self.context_manager.dependencies:
                                    g[dependency.__name__] = dependency

                                # TODO: this is a hack to tzutc in the eval, should be more robust
                                g["tzutc"] = tzutc
                                g["datetime"] = datetime
                                # finally, eval the expression
                                _arg = eval(_arg, g)
                            except ValueError:
                                pass
                    else:
                        _arg = arg.id
                    # if the value is empty '', we still need to pass it to the function
                    if _arg or _arg == "":
                        _args.append(_arg)
                # check if we need to inject tenant_id
                keep_func = getattr(keep_functions, func.attr)
                func_signature = inspect.signature(keep_func)

                kwargs = {}
                if "kwargs" in func_signature.parameters:
                    kwargs["tenant_id"] = self.context_manager.tenant_id

                try:
                    val = (
                        keep_func(*_args) if not kwargs else keep_func(*_args, **kwargs)
                    )
                # try again but with replacing \n with \\n
                # again - best effort see test_openobserve_rows_bug test
                except ValueError:
                    _args = [arg.replace("\n", "\\n") for arg in _args]
                    val = (
                        keep_func(*_args) if not kwargs else keep_func(*_args, **kwargs)
                    )
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
                    tree = ast.parse(t)
            else:
                # for strings such as "45%\n", we need to escape
                tree = ast.parse(token.encode("unicode_escape"))
        return _parse(self, tree)

    def _render(self, key: str, safe=False, default=""):
        if "{{^" in key or "{{ ^" in key:
            self.logger.debug(
                "Safe render is not supported when there are inverted sections."
            )
            safe = False

        # allow {{ const.<key> }} to be rendered
        const_rendering = False
        if key.startswith("{{ consts.") and key.endswith("}}"):
            self.logger.debug("Rendering const key")
            const_rendering = True

        context = self.context_manager.get_full_context()
        # TODO: protect from multithreaded where another thread will print to stderr, but thats a very rare case and we shouldn't care much
        original_stderr = sys.stderr
        sys.stderr = io.StringIO()
        rendered = chevron.render(key, context, warn=True)
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
                err = stderr_output.replace("\n", "")
            raise RenderException(f"{err} in the context.")
        if not rendered:
            return default

        if const_rendering:
            # https://github.com/keephq/keep/issues/2326
            rendered = html.unescape(rendered)
            return self._render(rendered, safe, default)
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


if __name__ == "__main__":
    # debug & test
    context_manager = ContextManager("keep")
    context_manager.event_context = {
        "ticket_id": "1234",
        "severity": "high",
        "ticket_created_at": "2021-09-01T00:00:00Z",
    }
    iohandler = IOHandler(context_manager)
    res = iohandler.render(
        iohandler.quote(
            "not '{{ alert.ticket_id }}' or (('{{ alert.ticket_status }}' in ['Resolved', 'Closed', 'Canceled']) and ('{{ alert.severity }}' == 'critical' or keep.datetime_compare(keep.utcnow(), keep.to_utc('{{ alert.ticket_created_at }}')) > 168))"
        ),
        safe=False,
    )
    from asteval import Interpreter

    aeval = Interpreter()
    evaluated_if_met = aeval(res)
    print(evaluated_if_met)
