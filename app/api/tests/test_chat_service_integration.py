"""Integration tests for the ChatService."""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock
from uuid import uuid4

from app.services.chat_service import ChatService, MAX_FUNCTION_CALL_ITERATIONS


class MockGeminiResponse:
    """Mock Gemini response object."""

    def __init__(self, text=None, function_call=None):
        self.candidates = [MagicMock()]
        content = MagicMock()
        self.candidates[0].content = content

        if function_call:
            part = MagicMock()
            part.function_call = MagicMock()
            part.function_call.name = function_call["name"]
            part.function_call.args = function_call.get("args", {})
            part.text = None
            part.thought_signature = None
            content.parts = [part]
        elif text:
            part = MagicMock()
            part.function_call = None
            part.text = text
            content.parts = [part]
        else:
            content.parts = []


class TestMaxIterationLimit:
    """Test that the function calling loop respects the max iteration limit."""

    @pytest.mark.asyncio
    @patch("app.services.chat_service.get_llm_provider")
    @patch("app.services.chat_service.gemini_breaker")
    @patch("app.services.chat_service.conversation_crud")
    async def test_loop_stops_at_max_iterations(
        self, mock_crud, mock_breaker, mock_get_provider, db_session
    ):
        """Verify the loop terminates at MAX_FUNCTION_CALL_ITERATIONS."""
        mock_breaker.allow_request.return_value = True
        mock_breaker.record_success = MagicMock()
        mock_breaker.record_failure = MagicMock()

        # Mock conversation CRUD
        mock_conversation = MagicMock()
        mock_conversation.id = uuid4()
        mock_conversation.context = {}
        mock_crud.get = AsyncMock(return_value=None)
        mock_crud.create_conversation = AsyncMock(return_value=mock_conversation)
        mock_crud.add_message = AsyncMock(return_value=MagicMock(
            id=uuid4(), created_at="2024-01-01T00:00:00Z"
        ))
        mock_crud.get_recent_messages = AsyncMock(return_value=[])
        mock_crud.update_context = AsyncMock()

        # Create a provider that always returns function calls
        mock_provider = MagicMock()
        mock_provider.build_config.return_value = MagicMock()
        mock_provider.build_content.return_value = MagicMock()
        mock_provider.convert_function_declarations.return_value = []

        infinite_fc = MockGeminiResponse(function_call={
            "name": "check_product_cache",
            "args": {"product_name": "Test"}
        })

        mock_provider.generate = AsyncMock(return_value=infinite_fc)
        mock_provider.has_function_call.return_value = True
        mock_provider.extract_function_call.return_value = {
            "name": "check_product_cache",
            "args": {"product_name": "Test"}
        }
        mock_provider.extract_function_call_part.return_value = MagicMock()
        mock_provider.extract_text.return_value = ""
        mock_provider.build_function_response.return_value = [MagicMock()]

        mock_get_provider.return_value = mock_provider

        with patch("app.services.chat_service.execute_function", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"status": "not_found"}

            chat_service = ChatService(db_session)

            from app.schemas.chat import ChatRequest
            request = ChatRequest(message="Tell me about Test Product")

            response = await chat_service.process_message(request)

            # Should have called execute_function exactly MAX_FUNCTION_CALL_ITERATIONS times
            assert mock_exec.call_count == MAX_FUNCTION_CALL_ITERATIONS
            assert "processing limit" in response.message.content


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with ChatService."""

    @pytest.mark.asyncio
    @patch("app.services.chat_service.get_llm_provider")
    @patch("app.services.chat_service.gemini_breaker")
    @patch("app.services.chat_service.conversation_crud")
    async def test_returns_graceful_error_when_breaker_open(
        self, mock_crud, mock_breaker, mock_get_provider, db_session
    ):
        """Verify graceful error when circuit breaker is OPEN."""
        mock_breaker.allow_request.return_value = False

        # Mock conversation CRUD
        mock_conversation = MagicMock()
        mock_conversation.id = uuid4()
        mock_conversation.context = {}
        mock_crud.get = AsyncMock(return_value=None)
        mock_crud.create_conversation = AsyncMock(return_value=mock_conversation)
        mock_crud.add_message = AsyncMock(return_value=MagicMock(
            id=uuid4(), created_at="2024-01-01T00:00:00Z"
        ))
        mock_crud.get_recent_messages = AsyncMock(return_value=[])
        mock_crud.update_context = AsyncMock()

        mock_provider = MagicMock()
        mock_provider.convert_function_declarations.return_value = []
        mock_get_provider.return_value = mock_provider

        chat_service = ChatService(db_session)

        from app.schemas.chat import ChatRequest
        request = ChatRequest(message="Tell me about iPhone 15")

        response = await chat_service.process_message(request)

        assert "experiencing issues" in response.message.content
        # generate should NOT have been called
        mock_provider.generate.assert_not_called()


class TestMultiProviderSelection:
    """Test that the correct LLM provider is used based on config."""

    @patch("app.services.llm_service.settings")
    def test_gemini_provider_selected(self, mock_settings):
        mock_settings.LLM_PROVIDER = "gemini"
        mock_settings.GEMINI_API_KEY = "test-key"
        mock_settings.LLM_MODEL = "gemini-3-flash-preview"

        from app.services.llm_service import get_llm_provider, GeminiProvider
        with patch("app.services.llm_service.GeminiProvider.__init__", return_value=None):
            provider = get_llm_provider()
            assert isinstance(provider, GeminiProvider)

    @patch("app.services.llm_service.settings")
    def test_openai_provider_selected(self, mock_settings):
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.OPENAI_API_KEY = "test-key"
        mock_settings.OPENAI_MODEL = "gpt-4o"

        from app.services.llm_service import get_llm_provider, OpenAIProvider
        with patch("app.services.llm_service.OpenAIProvider.__init__", return_value=None):
            provider = get_llm_provider()
            assert isinstance(provider, OpenAIProvider)

    @patch("app.services.llm_service.settings")
    def test_openai_requires_api_key(self, mock_settings):
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.OPENAI_API_KEY = ""

        from app.services.llm_service import get_llm_provider
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            get_llm_provider()

    @patch("app.services.llm_service.settings")
    def test_gemini_requires_api_key(self, mock_settings):
        mock_settings.LLM_PROVIDER = "gemini"
        mock_settings.GEMINI_API_KEY = ""

        from app.services.llm_service import get_llm_provider
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            get_llm_provider()


class TestFunctionCallingSequence:
    """Test that normal function calling sequences work correctly."""

    @pytest.mark.asyncio
    @patch("app.services.chat_service.get_llm_provider")
    @patch("app.services.chat_service.gemini_breaker")
    @patch("app.services.chat_service.conversation_crud")
    async def test_function_call_then_text_response(
        self, mock_crud, mock_breaker, mock_get_provider, db_session
    ):
        """Test: model returns function_call, then text response."""
        mock_breaker.allow_request.return_value = True
        mock_breaker.record_success = MagicMock()

        mock_conversation = MagicMock()
        mock_conversation.id = uuid4()
        mock_conversation.context = {}
        mock_crud.get = AsyncMock(return_value=None)
        mock_crud.create_conversation = AsyncMock(return_value=mock_conversation)
        mock_crud.add_message = AsyncMock(return_value=MagicMock(
            id=uuid4(), created_at="2024-01-01T00:00:00Z"
        ))
        mock_crud.get_recent_messages = AsyncMock(return_value=[])
        mock_crud.update_context = AsyncMock()

        mock_provider = MagicMock()
        mock_provider.build_config.return_value = MagicMock()
        mock_provider.build_content.return_value = MagicMock()
        mock_provider.convert_function_declarations.return_value = []

        # First call: function_call, Second call: text response
        call_count = 0
        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockGeminiResponse(function_call={
                    "name": "check_product_cache",
                    "args": {"product_name": "iPhone"}
                })
            return MockGeminiResponse(text="Here's what I found about the iPhone.")

        mock_provider.generate = AsyncMock(side_effect=mock_generate)

        # has_function_call returns True then False
        fc_count = 0
        def mock_has_fc(response):
            nonlocal fc_count
            fc_count += 1
            return fc_count == 1

        mock_provider.has_function_call.side_effect = mock_has_fc
        mock_provider.extract_function_call.return_value = {
            "name": "check_product_cache",
            "args": {"product_name": "iPhone"}
        }
        mock_provider.extract_function_call_part.return_value = MagicMock()
        mock_provider.extract_text.return_value = "Here's what I found about the iPhone."
        mock_provider.build_function_response.return_value = [MagicMock()]

        mock_get_provider.return_value = mock_provider

        with patch("app.services.chat_service.execute_function", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"status": "not_found"}

            chat_service = ChatService(db_session)

            from app.schemas.chat import ChatRequest
            request = ChatRequest(message="Tell me about iPhone")
            response = await chat_service.process_message(request)

            assert response.message.content == "Here's what I found about the iPhone."
            assert mock_exec.call_count == 1
