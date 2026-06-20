#!/usr/bin/env python3
"""Test the three new MCP tools against the live Crom API."""
import asyncio
import sys

from server import (
    CromGetUserInput,
    CromSearchByTagInput,
    CromSearchByAuthorInput,
    AttributionType,
    DetailLevel,
    crom_get_user,
    crom_search_by_tag,
    crom_search_by_author,
)

async def test_get_user():
    """Test crom_get_user."""
    print("=" * 60)
    print("Test 1: crom_get_user('W Asriel')")
    print("=" * 60)
    try:
        result = await crom_get_user(CromGetUserInput(user_name="W Asriel"))
        print(result[:500])
        print()
        return "W Asriel" in result
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def test_search_by_tag():
    """Test crom_search_by_tag."""
    print("=" * 60)
    print("Test 2: crom_search_by_tag(tag='scp', site='scp-cn', limit=3)")
    print("=" * 60)
    try:
        result = await crom_search_by_tag(
            CromSearchByTagInput(tag="scp", site="scp-cn", limit=3)
        )
        print(result[:1000])
        print()
        return "标签搜索" in result
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def test_search_by_author_all():
    """Test crom_search_by_author — ALL types."""
    print("=" * 60)
    print("Test 3: crom_search_by_author('W Asriel', type=ALL, limit=3)")
    print("=" * 60)
    try:
        result = await crom_search_by_author(
            CromSearchByAuthorInput(
                author_name="W Asriel",
                attribution_type=AttributionType.ALL,
                limit=3,
            )
        )
        print(result[:1000])
        print()
        return "作者搜索" in result
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def test_search_by_author_translator():
    """Test crom_search_by_author — TRANSLATOR only."""
    print("=" * 60)
    print("Test 4: crom_search_by_author('W Asriel', type=TRANSLATOR, limit=3)")
    print("=" * 60)
    try:
        result = await crom_search_by_author(
            CromSearchByAuthorInput(
                author_name="W Asriel",
                attribution_type=AttributionType.TRANSLATOR,
                limit=3,
            )
        )
        print(result[:1000])
        print()
        return "作者搜索" in result
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def test_search_by_tag_full():
    """Test crom_search_by_tag with full detail."""
    print("=" * 60)
    print("Test 5: crom_search_by_tag(tag='keter', detail_level='full', limit=2)")
    print("=" * 60)
    try:
        result = await crom_search_by_tag(
            CromSearchByTagInput(tag="keter", detail_level=DetailLevel.FULL, limit=2)
        )
        print(result[:1500])
        print()
        return "标签搜索" in result
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def test_author_with_site():
    """Test crom_search_by_author with site filter + AUTHOR only."""
    print("=" * 60)
    print("Test 6: crom_search_by_author('W Asriel', type=AUTHOR, site='scp-cn', limit=3)")
    print("=" * 60)
    try:
        result = await crom_search_by_author(
            CromSearchByAuthorInput(
                author_name="W Asriel",
                attribution_type=AttributionType.AUTHOR,
                site="scp-cn",
                limit=3,
            )
        )
        print(result[:1000])
        print()
        return "作者搜索" in result
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def main():
    results = []
    results.append(("get_user", await test_get_user()))
    results.append(("search_by_tag", await test_search_by_tag()))
    results.append(("search_by_author_ALL", await test_search_by_author_all()))
    results.append(("search_by_author_TRANSLATOR", await test_search_by_author_translator()))
    results.append(("search_by_tag_full", await test_search_by_tag_full()))
    results.append(("author_with_site", await test_author_with_site()))

    print("=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n  {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
