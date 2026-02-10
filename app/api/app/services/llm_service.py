"""Multi-provider LLM service supporting Gemini and OpenAI."""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.circuit_breaker import gemini_breaker
from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseLLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    async def generate(self, contents: List[Any], config: Any, tools: Any = None) -> Any:
        """Make an LLM call and return the raw response object."""

    @abstractmethod
    def has_function_call(self, response: Any) -> bool:
        """Check if the response contains a function call."""

    @abstractmethod
    def extract_function_call(self, response: Any) -> Optional[Dict[str, Any]]:
        """Extract function name and args from a function call response.

        Returns: {"name": str, "args": dict} or None
        """

    @abstractmethod
    def extract_function_call_part(self, response: Any) -> Any:
        """Extract the raw part/object containing the function call (for thought_signature etc)."""

    @abstractmethod
    def extract_text(self, response: Any) -> str:
        """Extract text content from the response."""

    @abstractmethod
    def build_function_response(
        self, name: str, result: Dict[str, Any], response: Any, function_call_part: Any
    ) -> List[Any]:
        """Build content items to append to conversation after function execution.

        Returns a list of content items to append (model response + function result).
        """

    @abstractmethod
    def build_content(self, role: str, text: str) -> Any:
        """Create a content object for the given role and text."""

    @abstractmethod
    def convert_function_declarations(self, declarations: List[Dict[str, Any]]) -> Any:
        """Convert function declarations to provider-specific format."""

    @abstractmethod
    def build_config(self, system_instruction: str, tools: Any, **kwargs) -> Any:
        """Build provider-specific generation config."""


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider."""

    def __init__(self):
        from google import genai
        from google.genai import types

        self.genai = genai
        self.types = types
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.LLM_MODEL

    async def generate(self, contents: List[Any], config: Any, tools: Any = None) -> Any:
        return await self.client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

    def has_function_call(self, response: Any) -> bool:
        try:
            if not response.candidates:
                return False
            content = response.candidates[0].content
            if not content or not content.parts:
                return False
            parts = content.parts
            return (
                hasattr(parts[0], "function_call")
                and parts[0].function_call
                and parts[0].function_call.name
            )
        except (AttributeError, IndexError):
            return False

    def extract_function_call(self, response: Any) -> Optional[Dict[str, Any]]:
        part = self.extract_function_call_part(response)
        if part and part.function_call:
            fc = part.function_call
            return {
                "name": fc.name,
                "args": dict(fc.args) if fc.args else {},
            }
        return None

    def extract_function_call_part(self, response: Any) -> Any:
        try:
            if not response.candidates:
                return None
            content = response.candidates[0].content
            if not content or not content.parts:
                return None
            for part in content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    return part
            return None
        except (AttributeError, IndexError):
            return None

    def extract_text(self, response: Any) -> str:
        try:
            if not response.candidates:
                return ""
            content = response.candidates[0].content
            if not content or not content.parts:
                return ""
            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    return part.text
            return ""
        except (AttributeError, IndexError):
            return ""

    def build_function_response(
        self, name: str, result: Dict[str, Any], response: Any, function_call_part: Any
    ) -> List[Any]:
        types = self.types

        # Append the complete model response to preserve thought_signature
        model_content = response.candidates[0].content
        items = [model_content]

        # Extract thought_signature from the function call part
        thought_sig = getattr(function_call_part, "thought_signature", None)

        if thought_sig:
            function_response_part = types.Part(
                function_response=types.FunctionResponse(
                    name=name,
                    response={"result": json.dumps(result)},
                ),
                thought_signature=thought_sig,
            )
        else:
            function_response_part = types.Part.from_function_response(
                name=name,
                response={"result": json.dumps(result)},
            )

        items.append(
            types.Content(role="user", parts=[function_response_part])
        )
        return items

    def build_content(self, role: str, text: str) -> Any:
        return self.types.Content(
            role=role,
            parts=[self.types.Part(text=text)],
        )

    def convert_function_declarations(self, declarations: List[Dict[str, Any]]) -> Any:
        types = self.types
        function_decls = []
        for func in declarations:
            properties = {}
            for param_name, param_schema in func["parameters"]["properties"].items():
                properties[param_name] = self._convert_param_schema(param_schema)

            func_decl = types.FunctionDeclaration(
                name=func["name"],
                description=func["description"],
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties=properties,
                    required=func["parameters"].get("required", []),
                ),
            )
            function_decls.append(func_decl)

        return [types.Tool(function_declarations=function_decls)]

    def _convert_param_schema(self, param: Dict[str, Any]) -> Any:
        types = self.types
        type_mapping = {
            "string": types.Type.STRING,
            "integer": types.Type.INTEGER,
            "number": types.Type.NUMBER,
            "boolean": types.Type.BOOLEAN,
            "array": types.Type.ARRAY,
            "object": types.Type.OBJECT,
        }
        schema_type = type_mapping.get(param.get("type", "string"), types.Type.STRING)
        schema_kwargs: Dict[str, Any] = {"type": schema_type}
        if "description" in param:
            schema_kwargs["description"] = param["description"]
        if "enum" in param:
            schema_kwargs["enum"] = param["enum"]
        if param.get("type") == "array" and "items" in param:
            items_type = type_mapping.get(
                param["items"].get("type", "string"), types.Type.STRING
            )
            schema_kwargs["items"] = types.Schema(type=items_type)
        return types.Schema(**schema_kwargs)

    def build_config(self, system_instruction: str, tools: Any, **kwargs) -> Any:
        return self.types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=tools,
            **kwargs,
        )


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider."""

    def __init__(self):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self._system_instruction: Optional[str] = None
        self._tools: Optional[List[Dict[str, Any]]] = None

    async def generate(self, contents: List[Any], config: Any, tools: Any = None) -> Any:
        """Generate using OpenAI chat completions."""
        messages = self._contents_to_messages(contents, config)
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        # Extract config params
        if config and isinstance(config, dict):
            if "temperature" in config:
                kwargs["temperature"] = config["temperature"]
            if "top_p" in config:
                kwargs["top_p"] = config["top_p"]
            if "max_output_tokens" in config:
                kwargs["max_completion_tokens"] = config["max_output_tokens"]

        if self._tools:
            kwargs["tools"] = self._tools

        return await self.client.chat.completions.create(**kwargs)

    def _contents_to_messages(self, contents: List[Any], config: Any) -> List[Dict[str, Any]]:
        """Convert our content list into OpenAI messages format."""
        messages = []

        # Add system instruction
        sys_instruction = None
        if config and hasattr(config, "system_instruction"):
            sys_instruction = config.system_instruction
        elif config and isinstance(config, dict):
            sys_instruction = config.get("system_instruction")

        if sys_instruction:
            messages.append({"role": "system", "content": sys_instruction})

        for content in contents:
            if isinstance(content, dict):
                messages.append(content)
            elif hasattr(content, "role"):
                # Gemini-style Content object — convert
                role = "assistant" if content.role == "model" else content.role
                if hasattr(content, "parts"):
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            messages.append({"role": role, "content": part.text})
                        elif hasattr(part, "function_response") and part.function_response:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": getattr(part.function_response, "_tool_call_id", "call_0"),
                                "content": json.dumps(part.function_response.response) if hasattr(part.function_response, "response") else "",
                            })
            else:
                messages.append({"role": "user", "content": str(content)})

        return messages

    def has_function_call(self, response: Any) -> bool:
        try:
            choice = response.choices[0]
            return bool(choice.message.tool_calls)
        except (AttributeError, IndexError):
            return False

    def extract_function_call(self, response: Any) -> Optional[Dict[str, Any]]:
        try:
            tool_call = response.choices[0].message.tool_calls[0]
            return {
                "name": tool_call.function.name,
                "args": json.loads(tool_call.function.arguments) if tool_call.function.arguments else {},
            }
        except (AttributeError, IndexError, json.JSONDecodeError):
            return None

    def extract_function_call_part(self, response: Any) -> Any:
        """For OpenAI, return the tool_call object."""
        try:
            return response.choices[0].message.tool_calls[0]
        except (AttributeError, IndexError):
            return None

    def extract_text(self, response: Any) -> str:
        try:
            content = response.choices[0].message.content
            return content or ""
        except (AttributeError, IndexError):
            return ""

    def build_function_response(
        self, name: str, result: Dict[str, Any], response: Any, function_call_part: Any
    ) -> List[Any]:
        """Build OpenAI-format messages for function response."""
        # Append the assistant message with tool_calls
        assistant_msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": function_call_part.id,
                    "type": "function",
                    "function": {
                        "name": function_call_part.function.name,
                        "arguments": function_call_part.function.arguments,
                    },
                }
            ],
        }

        # Append the tool result
        tool_msg = {
            "role": "tool",
            "tool_call_id": function_call_part.id,
            "content": json.dumps(result),
        }

        return [assistant_msg, tool_msg]

    def build_content(self, role: str, text: str) -> Any:
        return {"role": role, "content": text}

    def convert_function_declarations(self, declarations: List[Dict[str, Any]]) -> Any:
        """Convert function declarations to OpenAI tool format."""
        tools = []
        for func in declarations:
            tool = {
                "type": "function",
                "function": {
                    "name": func["name"],
                    "description": func["description"],
                    "parameters": func["parameters"],
                },
            }
            tools.append(tool)
        self._tools = tools
        return tools

    def build_config(self, system_instruction: str, tools: Any, **kwargs) -> Dict[str, Any]:
        """Build a config dict for OpenAI (stored as plain dict)."""
        config: Dict[str, Any] = {"system_instruction": system_instruction}
        config.update(kwargs)
        return config


def get_llm_provider() -> BaseLLMProvider:
    """Factory: return the configured LLM provider."""
    provider_name = settings.LLM_PROVIDER.lower()

    if provider_name == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        logger.info(f"Using OpenAI provider (model: {settings.OPENAI_MODEL})")
        return OpenAIProvider()

    # Default to Gemini
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
    logger.info(f"Using Gemini provider (model: {settings.LLM_MODEL})")
    return GeminiProvider()
