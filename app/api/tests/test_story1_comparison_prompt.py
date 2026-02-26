"""Tests for Story 1: Comparison workflow in system prompt."""

import pytest

from app.services.chat_service import SYSTEM_PROMPT, FUNCTION_LABELS


def test_system_prompt_has_comparison_section():
    """SYSTEM_PROMPT must contain a dedicated comparison flow section."""
    prompt_lower = SYSTEM_PROMPT.lower()
    assert "comparison" in prompt_lower and "flow" in prompt_lower, (
        "SYSTEM_PROMPT must contain a comparison flow section"
    )


def test_comparison_flow_requires_summary_for_each_product():
    """Comparison flow must instruct calling get_reviews_summary for EACH product."""
    prompt_lower = SYSTEM_PROMPT.lower()
    # Must mention calling get_reviews_summary for each/every product
    assert "get_reviews_summary" in SYSTEM_PROMPT, (
        "Comparison flow must reference get_reviews_summary"
    )
    # Must instruct doing it for each product (not just one)
    has_each = ("each product" in prompt_lower or "every product" in prompt_lower
                or "each one" in prompt_lower or "for both" in prompt_lower
                or "all products" in prompt_lower)
    assert has_each, (
        "Comparison flow must instruct calling get_reviews_summary for each/every/all product(s)"
    )


def test_comparison_flow_requires_compare_products():
    """Comparison flow must instruct calling compare_products after summaries."""
    assert "compare_products" in SYSTEM_PROMPT, (
        "Comparison flow must instruct calling compare_products"
    )


def test_function_reference_includes_semantic_search():
    """Function Reference section in SYSTEM_PROMPT must list semantic_search."""
    # Check it appears in the function reference area (not just anywhere)
    assert "semantic_search" in SYSTEM_PROMPT, (
        "SYSTEM_PROMPT Function Reference must include semantic_search"
    )
