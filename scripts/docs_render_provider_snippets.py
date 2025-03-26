""" """

import argparse
import glob
import os
import ast
import re
import sys
import time
from docstring_parser import parse
from jinja2 import Template


def get_attribute_name(node: ast.Attribute) -> str:
    """Get the full name of an attribute node (e.g., module.Class)"""
    parts = []
    current = node

    # Build name from right to left
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value

    if isinstance(current, ast.Name):
        parts.append(current.id)

    # Reverse and join with dots
    return ".".join(reversed(parts))


def is_dataclasses_field(node: ast.Call) -> bool:
    """Check if a Call node is dataclasses.field()"""
    if isinstance(node.func, ast.Name) and node.func.id == "field":
        return True
    if isinstance(node.func, ast.Attribute) and node.func.attr == "field":
        if (
            isinstance(node.func.value, ast.Name)
            and node.func.value.id == "dataclasses"
        ):
            return True
    return False


def extract_field_metadata(field_node: ast.Call):
    """Extract metadata dictionary from dataclasses.field() call"""
    metadata = {}

    for keyword in field_node.keywords:
        if keyword.arg == "metadata" and isinstance(keyword.value, ast.Dict):
            # Process each key-value pair in the metadata dict
            for i, key_node in enumerate(keyword.value.keys):
                if isinstance(key_node, ast.Constant) and i < len(keyword.value.values):
                    key = key_node.value
                    value_node = keyword.value.values[i]

                    # Extract value based on node type
                    if isinstance(value_node, ast.Constant):
                        metadata[key] = value_node.value
                    elif isinstance(value_node, ast.Name):
                        # For variables like True, False
                        if value_node.id == "True":
                            metadata[key] = True
                        elif value_node.id == "False":
                            metadata[key] = False
                        else:
                            metadata[key] = value_node.id

    return metadata


def extract_provider_class_insights(
    file_path: str,
) -> dict:
    """
    Extract the signature of the _notify and _query methods from a Python file.

    Args:
        file_path: Path to the Python file to analyze
    """

    result = {"auth": {}}

    # Read the file content
    with open(file_path, "r") as file:
        content = file.read()

    # Parse the Python code into an AST
    tree = ast.parse(content)

    provider_classes = []
    auth_classes = []

    # Search for provider and auth classes

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if isinstance(node, ast.ClassDef) and node.name.endswith("AuthConfig"):
                auth_classes.append(node)
            else:
                provider_classes.append(node)

    # Process each provider class and its _notify and _query methods

    for class_def in provider_classes:
        for method_def in class_def.body:
            if not isinstance(method_def, ast.FunctionDef):
                continue
            if method_def.name in ["_notify", "_query"]:
                args = []
                for arg in method_def.args.args:
                    if arg.arg != "self":  # Skip 'self' parameter
                        args.append(arg.arg)

                result[method_def.name] = {arg: "" for arg in args}
                # Extract docstring
                docstring = ast.get_docstring(method_def)
                if docstring:
                    # Parse docstring using docstring_parser
                    parsed_docstring = parse(docstring)

                    # Extract parameter descriptions
                    if parsed_docstring.params:
                        for param in parsed_docstring.params:
                            result[method_def.name][param.arg_name] = param.description

    # Process each auth class and its attributes

    for auth_class in auth_classes:
        # Look for attribute assignments with dataclasses.field
        for item in auth_class.body:
            if isinstance(item, ast.AnnAssign):
                field_name = (
                    item.target.id if isinstance(item.target, ast.Name) else None
                )

                # Get the field type annotation
                field_type = ""
                if isinstance(item.annotation, ast.Name):
                    field_type = item.annotation.id
                elif isinstance(item.annotation, ast.Attribute):
                    field_type = get_attribute_name(item.annotation)

                if field_name and item.value and isinstance(item.value, ast.Call):
                    if is_dataclasses_field(item.value):
                        field_metadata = extract_field_metadata(item.value)

                        # Create AuthConfigField with extracted info
                        description = field_metadata.get("description", "")
                        required = field_metadata.get("required", False)
                        sensitive = field_metadata.get("sensitive", False)
                        result["auth"][field_name] = {
                            "type": field_type,
                            "description": f"{description} (required: {required}, sensitive: {sensitive})",
                        }
    return result


def search_provider_mentions_in_examples(provider) -> dict[(str, str)]:
    """
    Search for provider mentions in the examples folder.

    Returns:
        A dictionary with provider names as keys and the example file paths where they are mentioned as values.
    """
    provider_mentions = {}
    for example in glob.glob("examples/**/workflows/**/*.y*ml", recursive=True):
        with open(example, "r") as file:
            content = file.read()

        file_name = os.path.relpath(example, "examples/workflows/")

        if provider in content:
            if provider not in provider_mentions:
                provider_mentions[file_name] = []
            provider_mentions[file_name].append(example)

    return provider_mentions


def check_AutoGeneratedSnippet_in_provider_documentation_files():
    """
    Check if AutoGeneratedSnippet is present in each provider documentation file.
    """
    missing_at = []
    providers = glob.glob("docs/providers/documentation/*.mdx")
    if len(providers) < 10:
        raise Exception(
            "There are less than 10 providers documentation files detected "
            "by AutoGeneratedSnippet tag validator, something went wrong."
        )
    for provider in providers:
        with open(provider, "r") as f:
            content = f.read()
            if "AutoGeneratedSnippet" not in content:
                missing_at.append(provider)
    return missing_at


documentation_template = """{/* This snippet is automatically generated using scripts/docs_render_provider_snippets.py 
Do not edit it manually, as it will be overwritten */}
{% if provider_data['auth'].items()|length == 0 %}{% else %}
## Authentication
This provider requires authentication.
{% for field, description in provider_data['auth'].items() -%}
- **{{ field }}**: {{ description.description }}
{% endfor %}
{% endif %}
## In workflows
{% if not "_query" in provider_data and not "_notify" in provider_data %}
This provider can't be used as a "step" or "action" in workflows. If you want to use it, please let us know by creating an issue in the [GitHub repository](https://github.com/keephq/keep/issues).
{% else %}
This provider can be used in workflows.

{% if "_query" in provider_data %}
As "step" to query data, example:
```yaml
steps:
    - name: Query {{ provider_name }}
      provider: {{ provider_name }}
      config: {% raw %}"{{ provider.my_provider_name }}"{% endraw %}
      with:
        {% for arg, description in provider_data["_query"].items() -%}
        {% if arg == "**kwargs" -%}# {{ description }}{% else -%}
        {{ arg }}: {value}  {% if description != "" %}# {{ description }}{% endif %}{% endif %}{% if not loop.last %}
        {% endif %}{% endfor %}
```
{% endif %}
{% if "_notify" in provider_data %}
As "action" to make changes or update data, example:
```yaml
actions:
    - name: Query {{ provider_name }}
      provider: {{ provider_name }}
      config: {% raw %}"{{ provider.my_provider_name }}"{% endraw %}
      with:
        {% for arg, description in provider_data["_notify"].items() -%}
        {% if arg == "**kwargs" -%}# {{ description }}{% else -%}
        {{ arg }}: {value}  {% if description != "" %}# {{ description }}{% endif %}{% endif %}{% if not loop.last %}
        {% endif %}{% endfor %}
```
{% endif %}
{% endif %}

{% if example_workflows.items()|length > 0 %}
Check the following workflow example{% if example_workflows.items()|length > 1 %}s{% endif %}:
{% for example_name, examples in example_workflows.items() -%}
{% for example in examples -%}
- [{{ example_name }}](https://github.com/keephq/keep/blob/main/{{ example }})
{% endfor -%}
{% endfor -%}
{% else %}
If you need workflow examples with this provider, please raise a [GitHub issue](https://github.com/keephq/keep/issues).
{% endif -%}
"""


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate if the generated snippets are up-to-date, otherwise exception",
    )
    args = parser.parse_args()

    if args.validate:
        print(
            """This script is responsible for generating provider documentation snippets.
It will check if the generated snippets are up-to-date.
It will also check if AutoGeneratedSnippet is present in each provider documentation file."""
        )
    else:
        print("Generating Provider documentation snippets...")

    providers = {}
    for provider in glob.glob("keep/providers/**/*_provider.py", recursive=True):
        provider_data = extract_provider_class_insights(provider)
        provider_name = os.path.basename(provider).replace("_provider.py", "")
        providers[provider_name] = provider_data

    outdated_files = []

    for provider_name, provider_data in providers.items():
        # Write snippet ../docs/snippets/providers_autogenerated/PROVIDER_NAME.md

        template = Template(documentation_template)
        template = template.render(
            provider_name=provider_name,
            provider_data=provider_data,
            example_workflows=search_provider_mentions_in_examples(provider_name),
        )

        # Validating if file exists and override if content is different.

        file_path = f"docs/snippets/providers/{provider_name}-snippet-autogenerated.mdx"
        is_outdated = True
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                existing_content = f.read()
                if existing_content == template:
                    is_outdated = False
                else:
                    # render the difference
                    print(f"File {file_path} is outdated.")
                    print("Existing content:")
                    print(existing_content)
                    print("New content:")
                    print(template)

        if is_outdated:
            outdated_files.append(file_path)
            if not args.validate:
                with open(file_path, "w") as f:
                    f.write(template)
                    # mintlify doesn't work nice with simultanious changes of multiple files
                    print(f"File {file_path} is outdated, updated.")
                    time.sleep(0.1)

    if args.validate:
        if outdated_files:
            print("The following files are outdated:")
            for file in outdated_files:
                print(f"- {file}")
            print("\nTo update them, run the following script:")
            print("python3 scripts/docs_render_provider_snippets.py")

        files_missing_autodocumentation_tag = (
            check_AutoGeneratedSnippet_in_provider_documentation_files()
        )

        if len(files_missing_autodocumentation_tag) > 0:
            print(
                "The following files are missing AutoGeneratedSnippet tag, it should be added manually. "
                "Refer to the other provider's documenations pages for the reference:"
            )
            for file in files_missing_autodocumentation_tag:
                print(f"- {file}")
        else:
            print("All files have AutoGeneratedSnippet tag. Nice!")

        if len(outdated_files) > 0 or len(files_missing_autodocumentation_tag) > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
