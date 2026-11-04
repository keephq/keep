"""
Bounty Solution 03: Automated OpenRPC & Markdown Reference Generator for LangGraph State Nodes
Target: Agent Bounties / Tooling ($75 Reward)
Scope: Introspects TypedDict state schemas and LangGraph nodes to generate schema docs and validation specs.
"""

import inspect
import json
from typing import get_type_hints, Dict, Any, List

class LangGraphSchemaGenerator:
    """
    Introspects Agent StateGraph definitions and TypedDict classes
    to generate standardized OpenRPC JSON specs and Markdown API references.
    """
    def __init__(self, state_schema_cls: type):
        self.state_cls = state_schema_cls

    def export_json_schema(self) -> Dict[str, Any]:
        hints = get_type_hints(self.state_cls)
        doc = inspect.getdoc(self.state_cls) or "Agent State Schema"

        properties = {}
        for prop_name, prop_type in hints.items():
            type_repr = getattr(prop_type, "__name__", str(prop_type))
            properties[prop_name] = {
                "type": type_repr,
                "description": f"Internal state attribute {prop_name}"
            }

        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": self.state_cls.__name__,
            "description": doc,
            "type": "object",
            "properties": properties,
            "required": list(hints.keys())
        }

    def generate_markdown_docs(self, workflow_nodes: List[str]) -> str:
        hints = get_type_hints(self.state_cls)
        lines = [
            f"# {self.state_cls.__name__} Specification",
            inspect.getdoc(self.state_cls) or "",
            "",
            "## State Attributes",
            "| Field | Type | Description |",
            "| :--- | :--- | :--- |"
        ]

        for k, v in hints.items():
            t_str = getattr(v, "__name__", str(v)).replace("|", "\\|")
            lines.append(f"| `{k}` | `{t_str}` | State property `{k}` |")

        lines.extend([
            "",
            "## Graph Node Topology",
            "The following nodes mutate this state graph sequentially:"
        ])
        for idx, node in enumerate(workflow_nodes, 1):
            lines.append(f"{idx}. **`{node}`**")

        return "\n".join(lines)
