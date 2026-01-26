"""Function calling module for Gemini integration."""

from app.functions.registry import FUNCTION_DECLARATIONS, execute_function

__all__ = ["FUNCTION_DECLARATIONS", "execute_function"]
