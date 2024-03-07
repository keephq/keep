"""
Grafana Provider is a class that allows to ingest/digest data from Grafana.
"""
import dataclasses
import random
from typing import Literal
import shlex
import subprocess
import json_repair

import pydantic
import requests

from keep.iohandler.iohandler import IOHandler
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory
import argparse
import json
import re
import sys


# whitespace is constrained to a single space char to prevent model "running away" in
# whitespace. Also maybe improves generation quality?
SPACE_RULE = '" "?'

PRIMITIVE_RULES = {
    'boolean': '("true" | "false") space',
    'number': '("-"? ([0-9] | [1-9] [0-9]*)) ("." [0-9]+)? ([eE] [-+]? [0-9]+)? space',
    'integer': '("-"? ([0-9] | [1-9] [0-9]*)) space',
    'string': r''' "\"" (
        [^"\\] |
        "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])
      )* "\"" space ''',
    'null': '"null" space',
}

INVALID_RULE_CHARS_RE = re.compile(r'[^a-zA-Z0-9-]+')
GRAMMAR_LITERAL_ESCAPE_RE = re.compile(r'[\r\n"]')
GRAMMAR_LITERAL_ESCAPES = {'\r': '\\r', '\n': '\\n', '"': '\\"'}


class SchemaConverter:
    def __init__(self, prop_order):
        self._prop_order = prop_order
        self._rules = {'space': SPACE_RULE}

    def _format_literal(self, literal):
        escaped = GRAMMAR_LITERAL_ESCAPE_RE.sub(
            lambda m: GRAMMAR_LITERAL_ESCAPES.get(
                m.group(0)), json.dumps(literal)
        )
        return f'"{escaped}"'

    def _add_rule(self, name, rule):
        esc_name = INVALID_RULE_CHARS_RE.sub('-', name)
        if esc_name not in self._rules or self._rules[esc_name] == rule:
            key = esc_name
        else:
            i = 0
            while f'{esc_name}{i}' in self._rules:
                i += 1
            key = f'{esc_name}{i}'
        self._rules[key] = rule
        return key

    def visit(self, schema, name):
        schema_type = schema.get('type')
        rule_name = name or 'root'

        if 'oneOf' in schema or 'anyOf' in schema:
            rule = ' | '.join((
                self.visit(alt_schema, f'{name}{"-" if name else ""}{i}')
                for i, alt_schema in enumerate(schema.get('oneOf') or schema['anyOf'])
            ))
            return self._add_rule(rule_name, rule)

        elif 'const' in schema:
            return self._add_rule(rule_name, self._format_literal(schema['const']))

        elif 'enum' in schema:
            rule = ' | '.join((self._format_literal(v)
                              for v in schema['enum']))
            return self._add_rule(rule_name, rule)

        elif schema_type == 'object' and 'properties' in schema:
            # TODO: `required` keyword
            prop_order = self._prop_order
            prop_pairs = sorted(
                schema['properties'].items(),
                # sort by position in prop_order (if specified) then by key
                key=lambda kv: (prop_order.get(kv[0], len(prop_order)), kv[0]),
            )

            rule = '"{" space'
            for i, (prop_name, prop_schema) in enumerate(prop_pairs):
                prop_rule_name = self.visit(
                    prop_schema, f'{name}{"-" if name else ""}{prop_name}')
                if i > 0:
                    rule += ' "," space'
                rule += fr' {self._format_literal(prop_name)} space ":" space {prop_rule_name}'
            rule += ' "}" space'

            return self._add_rule(rule_name, rule)

        elif schema_type == 'array' and 'items' in schema:
            # TODO `prefixItems` keyword
            item_rule_name = self.visit(
                schema['items'], f'{name}{"-" if name else ""}item')
            list_item_operator = f'("," space {item_rule_name})'
            successive_items = ""
            min_items = schema.get("minItems", 0)
            if min_items > 0:
                first_item = f"({item_rule_name})"
                successive_items = list_item_operator * (min_items - 1)
                min_items -= 1
            else:
                first_item = f"({item_rule_name})?"
            max_items = schema.get("maxItems")
            if max_items is not None and max_items > min_items:
                successive_items += (list_item_operator + "?") * \
                    (max_items - min_items - 1)
            else:
                successive_items += list_item_operator + "*"
            rule = f'"[" space {first_item} {successive_items} "]" space'
            return self._add_rule(rule_name, rule)

        else:
            assert schema_type in PRIMITIVE_RULES, f'Unrecognized schema: {schema}'
            return self._add_rule(
                'root' if rule_name == 'root' else schema_type,
                PRIMITIVE_RULES[schema_type]
            )

    def format_grammar(self):
        return '\n'.join((f'{name} ::= {rule}' for name, rule in self._rules.items()))


def main(args_in=None):
    parser = argparse.ArgumentParser(
        description='''
            Generates a grammar (suitable for use in ./main) that produces JSON conforming to a
            given JSON schema. Only a subset of JSON schema features are supported; more may be
            added in the future.
        ''',
    )
    parser.add_argument(
        '--prop-order',
        default=[],
        type=lambda s: s.split(','),
        help='''
            comma-separated property names defining the order of precedence for object properties;
            properties not specified here are given lower precedence than those that are, and are
            sorted alphabetically
        '''
    )
    parser.add_argument(
        'schema', help='file containing JSON schema ("-" for stdin)')
    args = parser.parse_args(args_in)

    schema = json.load(sys.stdin if args.schema == '-' else open(args.schema))
    prop_order = {name: idx for idx, name in enumerate(args.prop_order)}
    converter = SchemaConverter(prop_order)
    converter.visit(schema, '')
    print(converter.format_grammar())


@pydantic.dataclasses.dataclass
class AiProviderAuthConfig:
    """
    Ai provider backend host.
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "ollama host",
            "hint": "http://localhost:11434",
        },
    )


class AiProvider(BaseProvider):
    """
    """

    PROVIDER_DISPLAY_NAME = "AI Provider"

    provider_description = "AI Provider will enrich payload with missing fields."

    def generate_grammar_for_llm(schema):
        converter = SchemaConverter({})
        converter.visit(schema, '')
        return converter.format_grammar()

    def execute_model_with_grammar(text, schema):
        url = "http://localhost:8081/completion"
        headers = {"Content-Type": "application/json"}
        grammar = AiProvider.generate_grammar_for_llm(schema)

        prompt = f"""<s>[INST]
        {text}
        [/INST]
        """

        
        for _ in range(5):
            response = requests.post(url, headers=headers, json=data)
            cleaned_response = response.json()["content"].replace("\n", "")
            try:
                repaired_json = json_repair.loads(cleaned_response)
                repaired_json = {k: re.sub('[^A-Za-z0-9]+', '', v) for k, v in repaired_json.items()}
                
                return repaired_json
            except json.decoder.JSONDecodeError as e:
                print("Failed to parse response")
                print(e)
        return None

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.io_handler = IOHandler(context_manager=context_manager)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Grafana provider.

        """
        self.authentication_config = AiProviderAuthConfig(
            **self.config.authentication
        )

    def _query(self, field, free_speech_field_description, alert, **kwargs):

        # json_schema = {
        #     "type": "object",
        #     "properties": {
        #         field: {
        #             "type": "string",
        #             "description": free_speech_field_description,
        #         }
        #     },
        #     "required": [field],
        # }

        class AlertAnalysis(pydantic.BaseModel):
            severity: str = pydantic.Field(
                description=free_speech_field_description,
            )

        main_model_schema = AlertAnalysis.schema_json()  # (1)!
        
        return {
            field: AiProvider.execute_model_with_grammar("Alert: " + str(alert), json.loads(AlertAnalysis.schema_json()))[field],
        }

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[
                        logging.StreamHandler()])

    # Load environment variables
    import os

    host = os.environ.get("OLLAMA_HOST")
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = {
        "authentication": {"host": host},
    }
    provider: AiProvider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="ai-provider-id",
        provider_type="ai-provider",
        provider_config=config,
    )
