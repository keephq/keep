import unittest
from typing import TypedDict, List
from bounties.bounty_03_langgraph_docs import LangGraphSchemaGenerator

class SampleAgentState(TypedDict):
    """Execution state schema for quant order routing."""
    symbol: str
    target_vwap: float
    order_size: int
    executed_fills: List[dict]

class TestLangGraphSchemaGenerator(unittest.TestCase):
    def test_json_schema_export(self):
        generator = LangGraphSchemaGenerator(SampleAgentState)
        schema = generator.export_json_schema()

        self.assertEqual(schema["title"], "SampleAgentState")
        self.assertEqual(schema["type"], "object")
        self.assertIn("symbol", schema["properties"])
        self.assertIn("target_vwap", schema["properties"])
        self.assertEqual(len(schema["required"]), 4)

    def test_markdown_docs_generation(self):
        generator = LangGraphSchemaGenerator(SampleAgentState)
        nodes = ["fetch_orderbook", "calculate_vwap", "execute_twap_slice"]
        md = generator.generate_markdown_docs(nodes)

        self.assertIn("# SampleAgentState Specification", md)
        self.assertIn("| `symbol` |", md)
        self.assertIn("1. **`fetch_orderbook`**", md)
        self.assertIn("3. **`execute_twap_slice`**", md)

if __name__ == "__main__":
    unittest.main()
