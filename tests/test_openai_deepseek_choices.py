import unittest
from unittest.mock import MagicMock, patch
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.openai_provider.openai_provider import OpenaiProvider
from keep.providers.deepseek_provider.deepseek_provider import DeepseekProvider
from keep.providers.models.provider_config import ProviderConfig


class TestOpenAIDeepSeekEmptyChoices(unittest.TestCase):
    def setUp(self):
        self.context_manager = ContextManager(tenant_id="test", workflow_id="test")
        self.openai_config = ProviderConfig(
            id="openai-test",
            name="openai-test",
            authentication={"api_key": "fake-api-key"},
        )
        self.openai_provider = OpenaiProvider(
            context_manager=self.context_manager,
            provider_id="openai-test",
            config=self.openai_config,
        )

        self.deepseek_config = ProviderConfig(
            id="deepseek-test",
            name="deepseek-test",
            authentication={"api_key": "fake-api-key"},
        )
        self.deepseek_provider = DeepseekProvider(
            context_manager=self.context_manager,
            provider_id="deepseek-test",
            config=self.deepseek_config,
        )

    @patch("keep.providers.openai_provider.openai_provider.OpenAI")
    def test_openai_empty_choices(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.choices = []
        mock_client.chat.completions.create.return_value = mock_resp

        result = self.openai_provider._query(prompt="hello")
        self.assertEqual(result, {"response": ""})

    @patch("keep.providers.openai_provider.openai_provider.OpenAI")
    def test_openai_normal_choices(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = "pong"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_resp

        result = self.openai_provider._query(prompt="ping")
        self.assertEqual(result, {"response": "pong"})

    @patch("keep.providers.deepseek_provider.deepseek_provider.OpenAI")
    def test_deepseek_empty_choices(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.choices = []
        mock_client.chat.completions.create.return_value = mock_resp

        result = self.deepseek_provider._query(prompt="hello")
        self.assertEqual(result, {"response": ""})

    @patch("keep.providers.deepseek_provider.deepseek_provider.OpenAI")
    def test_deepseek_normal_choices(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = "pong"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_resp

        result = self.deepseek_provider._query(prompt="ping")
        self.assertEqual(result, {"response": "pong"})


if __name__ == "__main__":
    unittest.main()
