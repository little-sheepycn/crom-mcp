"""Quick test of the unified crom_search tool."""
import asyncio
import sys

from server import (
    CromUnifiedSearchInput,
    AttributionType,
    DetailLevel,
    crom_search,
)

async def test_author_and_tags():
    """Test: author + multiple tags."""
    print("=" * 60)
    print("Test: author='W Asriel' + tags=['scp', 'keter']")
    print("=" * 60)
    try:
        result = await crom_search(CromUnifiedSearchInput(
            author_name="W Asriel",
            tags=["scp", "keter"],
            limit=5,
        ))
        print(result[:1500])
        return "GraphQL" not in result
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_title_and_site():
    """Test: title + site."""
    print("=" * 60)
    print("Test: title='SCP-CN-001' + site='scp-cn'")
    print("=" * 60)
    try:
        result = await crom_search(CromUnifiedSearchInput(
            title="SCP-CN-001",
            site="scp-cn",
            limit=3,
        ))
        print(result[:1500])
        return "GraphQL" not in result
    except Exception as e:
        print(f"[FAIL] {e}")
        return False

async def test_tags_only():
    """Test: tags only (no author/title)."""
    print("=" * 60)
    print("Test: tags=['joke'] only")
    print("=" * 60)
    try:
        result = await crom_search(CromUnifiedSearchInput(
            tags=["joke"],
            limit=3,
            sort="rating_desc",
        ))
        print(result[:1500])
        return "GraphQL" not in result
    except Exception as e:
        print(f"[FAIL] {e}")
        return False

async def test_author_and_site():
    """Test: author + site only (no tags)."""
    print("=" * 60)
    print("Test: author='qntm' + site='scp-en'")
    print("=" * 60)
    try:
        result = await crom_search(CromUnifiedSearchInput(
            author_name="qntm",
            attribution_type=AttributionType.AUTHOR,
            site="scp-en",
            limit=3,
        ))
        print(result[:1500])
        return "GraphQL" not in result
    except Exception as e:
        print(f"[FAIL] {e}")
        return False

async def test_all_three():
    """Test: title + author + tags."""
    print("=" * 60)
    print("Test: title='SCP' + author='W Asriel' + tags=['scp']")
    print("=" * 60)
    try:
        result = await crom_search(CromUnifiedSearchInput(
            title="SCP",
            author_name="W Asriel",
            tags=["scp"],
            site="scp-cn",
            limit=3,
        ))
        print(result[:1500])
        return "GraphQL" not in result
    except Exception as e:
        print(f"[FAIL] {e}")
        return False

async def test_validation():
    """Test: no criteria should fail."""
    print("=" * 60)
    print("Test: empty input (should fail validation)")
    print("=" * 60)
    try:
        result = await crom_search(CromUnifiedSearchInput())
        print("First 100 chars:", result[:100])
        return "参数错误" in result or "至少需要" in result
    except Exception as e:
        print(f"[OK] Exception raised: {e}")
        return True

async def main():
    results = []
    results.append(("author+tags", await test_author_and_tags()))
    results.append(("title+site", await test_title_and_site()))
    results.append(("tags_only", await test_tags_only()))
    results.append(("author+site", await test_author_and_site()))
    results.append(("all_three", await test_all_three()))
    results.append(("validation", await test_validation()))

    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"\n  {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
