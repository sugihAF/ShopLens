#!/usr/bin/env python
"""Simple test runner to verify gather.py implementation."""

import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")
    try:
        from app.functions.registry import FUNCTION_DECLARATIONS, execute_function
        print("  ✓ registry imports work")

        from app.functions.gather import (
            gather_product_reviews,
            search_youtube_reviews,
            search_blog_reviews
        )
        print("  ✓ gather imports work")

        return True
    except Exception as e:
        print(f"  ✗ Import error: {e}")
        return False


def test_function_declarations():
    """Test that function declarations are correct."""
    print("\nTesting function declarations...")
    try:
        from app.functions.registry import FUNCTION_DECLARATIONS

        declared_names = [f["name"] for f in FUNCTION_DECLARATIONS]

        required_functions = [
            "gather_product_reviews",
            "search_youtube_reviews",
            "search_blog_reviews"
        ]

        for func_name in required_functions:
            if func_name in declared_names:
                print(f"  ✓ {func_name} is declared")
            else:
                print(f"  ✗ {func_name} is MISSING")
                return False

        return True
    except Exception as e:
        print(f"  ✗ Declaration error: {e}")
        return False


def test_function_registration():
    """Test that functions are registered in the registry."""
    print("\nTesting function registration...")
    try:
        from app.functions.registry import _FUNCTION_REGISTRY

        required_functions = [
            "gather_product_reviews",
            "search_youtube_reviews",
            "search_blog_reviews"
        ]

        for func_name in required_functions:
            if func_name in _FUNCTION_REGISTRY:
                print(f"  ✓ {func_name} is registered")
            else:
                print(f"  ✗ {func_name} is NOT registered")
                return False

        return True
    except Exception as e:
        print(f"  ✗ Registration error: {e}")
        return False


def test_gather_product_reviews_validation():
    """Test gather_product_reviews validates input."""
    print("\nTesting gather_product_reviews validation...")
    try:
        import asyncio
        from app.functions.gather import gather_product_reviews

        async def run_test():
            # Mock db session (we just need to test validation)
            class MockDB:
                pass

            # Test missing product_name
            result = await gather_product_reviews(MockDB(), {})
            if "error" in result:
                print(f"  ✓ Returns error for missing product_name: {result['error']}")
                return True
            else:
                print(f"  ✗ Should return error for missing product_name")
                return False

        return asyncio.run(run_test())
    except Exception as e:
        print(f"  ✗ Validation test error: {e}")
        return False


def test_search_youtube_validation():
    """Test search_youtube_reviews validates input."""
    print("\nTesting search_youtube_reviews validation...")
    try:
        import asyncio
        from app.functions.gather import search_youtube_reviews

        async def run_test():
            class MockDB:
                pass

            result = await search_youtube_reviews(MockDB(), {})
            if "error" in result:
                print(f"  ✓ Returns error for missing product_name: {result['error']}")
                return True
            else:
                print(f"  ✗ Should return error for missing product_name")
                return False

        return asyncio.run(run_test())
    except Exception as e:
        print(f"  ✗ Validation test error: {e}")
        return False


def test_search_blog_validation():
    """Test search_blog_reviews validates input."""
    print("\nTesting search_blog_reviews validation...")
    try:
        import asyncio
        from app.functions.gather import search_blog_reviews

        async def run_test():
            class MockDB:
                pass

            result = await search_blog_reviews(MockDB(), {})
            if "error" in result:
                print(f"  ✓ Returns error for missing product_name: {result['error']}")
                return True
            else:
                print(f"  ✗ Should return error for missing product_name")
                return False

        return asyncio.run(run_test())
    except Exception as e:
        print(f"  ✗ Validation test error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("ShopLens Phase 1 Test Runner")
    print("=" * 50)

    tests = [
        test_imports,
        test_function_declarations,
        test_function_registration,
        test_gather_product_reviews_validation,
        test_search_youtube_validation,
        test_search_blog_validation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ Test crashed: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)

    if failed == 0:
        print("\n✓ All tests PASSED!")
        sys.exit(0)
    else:
        print("\n✗ Some tests FAILED")
        sys.exit(1)
