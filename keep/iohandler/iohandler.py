import re

import chevron

import keep.functions as keep_functions


class IOHandler:
    def render(self, template, context):
        # check if inside the mustache is object in the context
        if template.count("}}") != template.count("{{"):
            raise Exception(
                f"Invalid template - number of }} and {{ does not match {template}"
            )
        # iterate all mustache that later invoked by a function and replace them with the context

        func, arg, _ = self._parse_mustache(template)
        val = self._get(context, arg)
        # if its just string manipulation
        if not func:
            return template.replace("{{" + arg + "}}", val)

        # remove the (
        func = func.strip("(")
        func = getattr(keep_functions, func)
        output = func(arg)
        return output

    def _parse_mustache(self, template):
        # Example with func
        #       template = 'len({{ steps.elastic-no-errors.results }})'
        #           =>    func = 'len(', arg = ' steps.elastic-no-errors.results ', _ = ')'
        # Example without func
        #      template = '{{ steps.elastic-no-errors.results }}'
        #          =>    func = '', arg = ' steps.elastic-no-errors.results ', _ = ''
        #
        # TODO: support more than one func
        res = re.split("({{.*?}})", template)
        res[1] = res[1].strip("{{").strip("}}")
        return res[0], res[1], res[2]

    def _get(self, context, key):
        key = key.strip()
        for k in key.split("."):
            if k in context:
                context = context[k]
            else:
                return None
        return context
