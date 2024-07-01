from argparse import ArgumentParser
import typing as t
import json

Json = dict[str | t.Literal["anyOf", "type"], "Json"] | list["Json"] | str | bool


## Reference: https://github.com/tiangolo/fastapi/discussions/9789
def convert_3_dot_1_to_3_dot_0(json: dict[str, Json]):
    """Will attempt to convert version 3.1.0 of some openAPI json into 3.0.2

    Usage:

        >>> from pprint import pprint
        >>> json = {
        ...     "some_irrelevant_keys": {...},
        ...     "nested_dict": {"nested_key": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
        ...     "examples": [{...}, {...}]
        ... }
        >>> convert_3_dot_1_to_3_dot_0(json)
        >>> pprint(json)
        {'example': {Ellipsis},
         'nested_dict': {'nested_key': {'anyOf': [{'type': 'string'}],
                                        'nullable': True}},
         'openapi': '3.0.2',
         'some_irrelevant_keys': {Ellipsis}}
    """
    json["openapi"] = "3.0.2"

    def inner(yaml_dict: Json):
        if isinstance(yaml_dict, dict):
            if "anyOf" in yaml_dict and isinstance((anyOf := yaml_dict["anyOf"]), list):
                for i, item in enumerate(anyOf):
                    if isinstance(item, dict) and item.get("type") == "null":
                        anyOf.pop(i)
                        yaml_dict["nullable"] = True
            if "examples" in yaml_dict:
                examples = yaml_dict["examples"]
                del yaml_dict["examples"]
                if isinstance(examples, list) and len(examples):
                    yaml_dict["example"] = examples[0]
            for value in yaml_dict.values():
                inner(value)
        elif isinstance(yaml_dict, list):
            for item in yaml_dict:
                inner(item)

    inner(json)
    return json

if __name__ == "__main__":

    parser = ArgumentParser(
        description="Script for converting openapi version 3.1.0 to 3.0.2"
    )
    parser.add_argument("-s", "--source", help="The path to openapi.json")
    parser.add_argument("-d", "--dest", help="The path to output")

    args = parser.parse_args()

    with open(args.source, "r") as fd:
        content = json.load(fd)

    output = json.dumps(convert_3_dot_1_to_3_dot_0(content))
    with open(args.dest, "wt") as wt:
        wt.write(output)
