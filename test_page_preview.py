#!/usr/bin/env python3
"""Test the crom_get_page_preview tool (Crom Aviary) against the live service."""
import asyncio
import sys

from server import (
    CromPagePreviewInput,
    crom_get_page_preview,
)


async def test_preview_scp_cn():
    """SCP-CN 页面（中文标题 + 审核中占位卡片）。"""
    print("=" * 60)
    print("Test 1: crom_get_page_preview(scp-cn-3969)")
    print("=" * 60)
    try:
        result = await crom_get_page_preview(
            CromPagePreviewInput(url="http://scp-wiki-cn.wikidot.com/scp-cn-3969")
        )
        print(result)
        ok = (
            "Aviary 链接" in result
            and "Discord 预览图" in result
            and "_embed?data=" in result
            and "&sig=" in result
        )
        return ok
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def test_preview_scp_en_full():
    """SCP-EN 页面（含 description 的完整卡片）。"""
    print("=" * 60)
    print("Test 2: crom_get_page_preview(scp-9182)")
    print("=" * 60)
    try:
        result = await crom_get_page_preview(
            CromPagePreviewInput(url="http://scp-wiki.wikidot.com/scp-9182")
        )
        print(result[:1500])
        return (
            "SCP-9182" in result
            and "_embed?data=" in result
            and "sig=" in result
        )
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def test_preview_https_normalized():
    """https:// 输入应被自动转换为 http:// 后仍能出图。"""
    print("=" * 60)
    print("Test 3: crom_get_page_preview(https://scp-wiki.wikidot.com/scp-9182)")
    print("=" * 60)
    try:
        result = await crom_get_page_preview(
            CromPagePreviewInput(url="https://scp-wiki.wikidot.com/scp-9182")
        )
        print(result[:800])
        return "Discord 预览图" in result and "scp-9182" in result.lower()
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def test_preview_not_found():
    """不存在的页面应返回友好错误而非崩溃。"""
    print("=" * 60)
    print("Test 4: crom_get_page_preview(不存在的页面)")
    print("=" * 60)
    try:
        result = await crom_get_page_preview(
            CromPagePreviewInput(
                url="http://scp-wiki-cn.wikidot.com/zzz-no-such-page-xyz"
            )
        )
        print(result)
        return "页面预览不可用" in result
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def test_preview_garbage_url():
    """非 Wikidot URL 应被优雅拒绝。"""
    print("=" * 60)
    print("Test 5: crom_get_page_preview(example.com)")
    print("=" * 60)
    try:
        result = await crom_get_page_preview(
            CromPagePreviewInput(url="http://example.com/some-page")
        )
        print(result)
        # Aviary 对站外 URL 同样返回 Page not found
        return "页面预览不可用" in result
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def main():
    results = []
    results.append(("preview_scp_cn", await test_preview_scp_cn()))
    results.append(("preview_scp_en_full", await test_preview_scp_en_full()))
    results.append(("preview_https_normalized", await test_preview_https_normalized()))
    results.append(("preview_not_found", await test_preview_not_found()))
    results.append(("preview_garbage_url", await test_preview_garbage_url()))

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
