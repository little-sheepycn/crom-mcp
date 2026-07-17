#!/usr/bin/env python3
"""
Crom MCP Server — 通过 Model Context Protocol 查询 Crom API v2.

Endpoint: https://apiv2.crom.avn.sh/graphql

默认行为：返回基本信息 + 作者（detail_level="basic"）。
当用户需要更多信息时，设置 detail_level="full" 获取完整字段。
"""

import json
import ssl
from enum import Enum
from typing import Optional

import httpx
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
import logging
import sys

# ---- 日志输出到 stderr，避免干扰 stdio 协议 ----
logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger("crom_mcp")

# ---- 初始化 MCP 服务 ----
mcp = FastMCP("crom_mcp")

ENDPOINT = "https://apiv2.crom.avn.sh/graphql"
PAGE_SIZE = 10

# ============================================================
# 字段定义
# ============================================================

# 接口通用字段 (ResolvedPage)
INTERFACE_FIELDS = {
    "url":               "页面 URL",
    "alternateTitles":   "替代标题列表",
    "attributions":      "作者/译者/改写者归属信息",
    "latestDiaryEntry":  "最新日记条目",
}

# WikidotPage 特有标量字段
WIKIDOT_SCALARS = [
    "title", "wikidotId", "rating", "voteCount", "category",
    "tags", "createdAt", "revisionCount", "commentCount",
    "isHidden", "isUserPage", "thumbnailUrl", "source", "textContent", "summary",
]

# 基本信息预设
BASIC_FIELDS = ["title", "rating", "voteCount", "category", "createdAt"]

# 基本信息 + 作者（默认返回）
BASIC_PLUS_AUTHOR_FIELDS = BASIC_FIELDS + ["createdBy", "attributions"]

# 完整字段
FULL_FIELDS = (
    BASIC_PLUS_AUTHOR_FIELDS
    + ["wikidotId", "tags", "revisionCount", "commentCount",
       "isHidden", "isUserPage", "thumbnailUrl", "parent", "children",
       "thread", "source", "textContent", "summary", "alternateTitles"]
)

# 排序选项
SORT_OPTIONS = {
    "rating_desc":  ("WIKIDOT_RATING", "DESC"),
    "rating_asc":   ("WIKIDOT_RATING", "ASC"),
    "date_desc":    ("WIKIDOT_CREATED_AT", "DESC"),
    "date_asc":     ("WIKIDOT_CREATED_AT", "ASC"),
    "title_asc":    ("WIKIDOT_TITLE", "ASC"),
    "latest_attr":  ("LATEST_ATTRIBUTION_DATE", "DESC"),
}

# 站点预设
SITE_PRESETS = {
    "scp-cn":    "http://scp-wiki-cn.wikidot.com/",
    "scp-en":    "http://scp-wiki.wikidot.com/",
    "scp-int":   "http://scp-int.wikidot.com/",
    "scp-ru":    "http://scp-ru.wikidot.com/",
    "scp-fr":    "http://fondationscp.wikidot.com/",
    "wanderers": "http://wanderers-library.wikidot.com/",
    "backrooms": "http://backrooms-wiki.wikidot.com/",
}

# ============================================================
# Pydantic 输入模型
# ============================================================

class DetailLevel(str, Enum):
    """信息详细程度。"""
    BASIC = "basic"
    FULL = "full"


class CromSearchInput(BaseModel):
    """按标题搜索页面的输入参数。"""
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        ...,
        description="页面标题关键字，支持模糊匹配（前缀匹配），例如 'scp-cn-001'、'SCP-173'",
        min_length=1, max_length=200,
    )
    site: Optional[str] = Field(
        default=None,
        description=f"限定站点范围，可选值: {', '.join(SITE_PRESETS.keys())}。不填则搜索全站。",
    )
    sort: str = Field(
        default="rating_desc",
        description=f"排序方式: {', '.join(SORT_OPTIONS.keys())}",
    )
    detail_level: DetailLevel = Field(
        default=DetailLevel.BASIC,
        description="信息详细程度: 'basic' 返回基本信息+作者（默认），'full' 返回全部字段（含源码、摘要、论坛帖子等）",
    )
    after: Optional[str] = Field(
        default=None,
        description="分页游标，传入上一次查询返回的 endCursor 以获取下一页结果",
    )
    limit: int = Field(default=10, description="返回条数", ge=1, le=100)


class CromGetPageInput(BaseModel):
    """按 URL 获取单个页面的输入参数。"""
    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(
        ...,
        description="页面的完整 Wikidot URL，例如 'http://scp-wiki-cn.wikidot.com/scp-cn-001'。注意必须用 http:// 而非 https://。",
        min_length=10, max_length=500,
    )
    detail_level: DetailLevel = Field(
        default=DetailLevel.BASIC,
        description="信息详细程度: 'basic' 返回基本信息+作者（默认），'full' 返回全部字段",
    )


class CromThreadInput(BaseModel):
    """获取论坛帖子的输入参数。"""
    model_config = ConfigDict(str_strip_whitespace=True)

    thread_id: str = Field(
        ...,
        description="Wikidot 论坛 thread ID",
        min_length=1, max_length=50,
    )


class CromPostInput(BaseModel):
    """获取论坛回帖的输入参数。"""
    model_config = ConfigDict(str_strip_whitespace=True)

    post_id: str = Field(
        ...,
        description="Wikidot 论坛 post ID",
        min_length=1, max_length=50,
    )


class ContentType(str, Enum):
    """返回内容类型。"""
    SOURCE = "source"
    TEXT = "text"
    BOTH = "both"


class AttributionType(str, Enum):
    """归属类型，用于 attributions 筛选。"""
    AUTHOR = "AUTHOR"
    TRANSLATOR = "TRANSLATOR"
    REWRITE = "REWRITE"
    ALL = "ALL"


class AuthorSearchMode(str, Enum):
    """[已废弃] 作者搜索模式 — 仅保留 attribution 模式。createdBy 不可筛选。"""
    ATTRIBUTION = "attribution"


class CromGetUserInput(BaseModel):
    """查询 Wikidot 用户信息的输入参数。"""
    model_config = ConfigDict(str_strip_whitespace=True)

    user_name: str = Field(
        ...,
        description="Wikidot 用户名（displayName），大小写不敏感精确匹配，例如 'W Asriel'、'drMikey'",
        min_length=1, max_length=200,
    )


class CromSearchByTagInput(BaseModel):
    """按标签搜索页面的输入参数。"""
    model_config = ConfigDict(str_strip_whitespace=True)

    tag: str = Field(
        ...,
        description="标签名（大小写不敏感精确匹配），例如 'scp'、'keter'、'joke'、'goi-format'、'safe'",
        min_length=1, max_length=100,
    )
    site: Optional[str] = Field(
        default=None,
        description=f"限定站点范围，可选值: {', '.join(SITE_PRESETS.keys())}。不填则搜索全站。",
    )
    sort: str = Field(
        default="rating_desc",
        description=f"排序方式: {', '.join(SORT_OPTIONS.keys())}",
    )
    detail_level: DetailLevel = Field(
        default=DetailLevel.BASIC,
        description="信息详细程度: 'basic' 返回基本信息+作者（默认），'full' 返回全部字段",
    )
    after: Optional[str] = Field(
        default=None,
        description="分页游标，传入上一次查询返回的 endCursor 以获取下一页结果",
    )
    limit: int = Field(default=10, description="返回条数", ge=1, le=100)


class CromSearchByAuthorInput(BaseModel):
    """按作者/归属信息搜索页面的输入参数。

    通过 attributions 字段筛选，支持按作者（AUTHOR）、译者（TRANSLATOR）、
    改写者（REWRITE）或全部（ALL）类型过滤。
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    author_name: str = Field(
        ...,
        description="作者/用户名称（大小写不敏感精确匹配），例如 'W Asriel'、'drMikey'",
        min_length=1, max_length=200,
    )
    attribution_type: AttributionType = Field(
        default=AttributionType.ALL,
        description="归属类型筛选: 'AUTHOR' 原创作者，'TRANSLATOR' 译者，'REWRITE' 改写者，'ALL' 全部（默认）",
    )
    site: Optional[str] = Field(
        default=None,
        description=f"限定站点范围，可选值: {', '.join(SITE_PRESETS.keys())}。不填则搜索全站。",
    )
    sort: str = Field(
        default="rating_desc",
        description=f"排序方式: {', '.join(SORT_OPTIONS.keys())}",
    )
    detail_level: DetailLevel = Field(
        default=DetailLevel.BASIC,
        description="信息详细程度: 'basic' 返回基本信息+作者（默认），'full' 返回全部字段",
    )
    after: Optional[str] = Field(
        default=None,
        description="分页游标，传入上一次查询返回的 endCursor 以获取下一页结果",
    )
    limit: int = Field(default=10, description="返回条数", ge=1, le=100)


class CromTopAuthorsInput(BaseModel):
    """获取作者排行榜的输入参数。

    通过 usersByRank_v1 按排名查询作者及其统计数据。
    每查询一位作者消耗 2 rate limit points。
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    site: Optional[str] = Field(
        default=None,
        description=f"限定站点范围。不填则查询全站（global）排名。可选值: {', '.join(SITE_PRESETS.keys())}",
    )
    limit: int = Field(
        default=10,
        description="返回上榜作者数量（每位消耗 2 pts）",
        ge=1, le=100,
    )
    start_rank: int = Field(
        default=1,
        description="起始排名（1 表示第一名）",
        ge=1, le=1000,
    )


class CromAuthorStatsInput(BaseModel):
    """查询单个作者统计数据的输入参数。"""
    model_config = ConfigDict(str_strip_whitespace=True)

    author_name: str = Field(
        ...,
        description="作者名（displayName），大小写不敏感精确匹配，例如 'W Asriel'",
        min_length=1, max_length=200,
    )


class CromPageSourceInput(BaseModel):
    """获取页面源码/纯文本的输入参数。"""
    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(
        ...,
        description="页面的完整 Wikidot URL，注意必须用 http://。",
        min_length=10, max_length=500,
    )
    content_type: ContentType = Field(
        default=ContentType.BOTH,
        description="返回内容类型: 'source' 仅 Wikidot 标记源码，'text' 仅纯文本，'both' 两者都返回（默认）",
    )


class CromUnifiedSearchInput(BaseModel):
    """统一搜索页面的输入参数 — 支持组合过滤条件。

    所有搜索条件均为可选，但至少需提供 title、author_name 或 tags 之一。
    多个条件之间为 AND 逻辑（同时满足）。
    多个 tags 之间为 AND 逻辑（页面必须同时含有所有指定标签）。
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = Field(
        default=None,
        description="页面标题关键字，支持模糊前缀匹配（同时搜索主标题和替代标题）",
        min_length=1, max_length=200,
    )
    author_name: Optional[str] = Field(
        default=None,
        description="作者/用户名称，大小写不敏感精确匹配",
        min_length=1, max_length=200,
    )
    attribution_type: AttributionType = Field(
        default=AttributionType.ALL,
        description="归属类型筛选（配合 author_name 使用）: 'AUTHOR' 原创，'TRANSLATOR' 翻译，'REWRITE' 改写，'ALL' 全部",
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="标签列表，大小写敏感精确匹配，多个标签为 AND 关系。例如 ['scp', 'keter'] 表示页面必须同时含有这两个标签",
    )
    site: Optional[str] = Field(
        default=None,
        description=f"限定站点范围，可选值: {', '.join(SITE_PRESETS.keys())}。不填则搜索全站。",
    )
    sort: str = Field(
        default="rating_desc",
        description=f"排序方式: {', '.join(SORT_OPTIONS.keys())}",
    )
    detail_level: DetailLevel = Field(
        default=DetailLevel.BASIC,
        description="信息详细程度: 'basic' 返回基本信息+作者（默认），'full' 返回全部字段",
    )
    after: Optional[str] = Field(
        default=None,
        description="分页游标，传入上一次查询返回的 endCursor 以获取下一页结果",
    )
    limit: int = Field(default=10, description="返回条数", ge=1, le=100)


class CromGetChildPagesInput(BaseModel):
    """获取子页面列表的输入参数。

    子页面是 Wikidot 中通过 parent 字段关联到当前页面的页面，
    常用于系列文章（如 SCP 系列、故事集等）的子集导航。
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(
        ...,
        description="父页面的完整 Wikidot URL，例如 'http://scp-wiki-cn.wikidot.com/scp-cn-001'。注意必须用 http://。",
        min_length=10, max_length=500,
    )
    detail_level: DetailLevel = Field(
        default=DetailLevel.BASIC,
        description="信息详细程度: 'basic' 返回基本信息+作者（默认），'full' 返回全部字段",
    )


# ============================================================
# 共享工具函数
# ============================================================

async def _gql_request(query: str) -> dict:
    """发送 GraphQL 请求并返回 JSON 响应。"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                ENDPOINT,
                json={"query": query},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"API 请求失败: HTTP {e.response.status_code}")
        except httpx.TimeoutException:
            raise RuntimeError("请求超时，请稍后重试。")
        except httpx.RequestError as e:
            raise RuntimeError(f"网络错误: {e}")


def _resolve_fields(detail_level: DetailLevel) -> list[str]:
    """根据 detail_level 返回要查询的字段列表。"""
    if detail_level == DetailLevel.FULL:
        return FULL_FIELDS
    return BASIC_PLUS_AUTHOR_FIELDS


def _build_graphql_selection(fields: list[str], base_indent: int = 8) -> str:
    """根据字段列表构建 GraphQL 选择片段。

    base_indent 控制顶层缩进（空格数），默认为 8（用于 pages 查询的 node 级别）。
    当用于 children 等嵌套场景时，传入 base_indent=10。
    """
    ind1 = " " * base_indent       # 顶层字段 / 块开始
    ind2 = " " * (base_indent + 2) # 子字段
    ind3 = " " * (base_indent + 4) # 孙字段
    ind4 = " " * (base_indent + 6) # 曾孙字段

    parts = []

    # 接口字段
    interface = [f for f in fields if f in INTERFACE_FIELDS]
    if "attributions" in interface:
        interface.remove("attributions")
        parts.append(f"""{ind1}attributions {{
{ind2}type
{ind2}user {{
{ind3}... on WikidotUser {{
{ind4}displayName
{ind4}wikidotId
{ind3}}}
{ind2}}}
{ind1}}}""")
    if "alternateTitles" in interface:
        interface.remove("alternateTitles")
        parts.append(f"""{ind1}alternateTitles {{
{ind2}title
{ind1}}}""")
    if "latestDiaryEntry" in interface:
        interface.remove("latestDiaryEntry")
        parts.append(f"""{ind1}latestDiaryEntry {{
{ind2}id
{ind2}title
{ind2}createdAt
{ind1}}}""")
    for f in interface:
        if f != "url":
            parts.append(f"{ind1}{f}")

    # WikidotPage 特化字段 — 全部合并到单个 inline fragment
    wikidot_body = []

    scalars = [f for f in fields if f in WIKIDOT_SCALARS]
    for f in scalars:
        wikidot_body.append(f"{ind2}{f}")

    if "createdBy" in fields:
        wikidot_body.append(f"""{ind2}createdBy {{
{ind3}displayName
{ind3}wikidotId
{ind2}}}""")
    if "parent" in fields:
        wikidot_body.append(f"""{ind2}parent {{
{ind3}url
{ind2}}}""")
    if "children" in fields:
        wikidot_body.append(f"""{ind2}children {{
{ind3}url
{ind2}}}""")
    if "thread" in fields:
        wikidot_body.append(f"""{ind2}thread {{
{ind3}threadId
{ind3}title
{ind3}postCount
{ind3}createdAt
{ind2}}}""")

    if wikidot_body:
        body = "\n".join(wikidot_body)
        parts.append(f"""{ind1}... on WikidotPage {{
{body}
{ind1}}}""")

    return "\n".join(parts)


def _format_page_node(node: dict, fields: list[str]) -> dict:
    """提取并扁平化 page node 中的字段到简单 dict。"""
    result = {}
    result["url"] = node.get("url", "")

    # 接口字段
    if "attributions" in fields:
        attrs = node.get("attributions") or []
        authors = []
        for a in attrs:
            user = (a.get("user") or {})
            name = user.get("displayName", "?")
            atype = a.get("type", "?")
            authors.append(f"{name}({atype})")
        result["attributions"] = ", ".join(authors) if authors else "-"

    if "alternateTitles" in fields:
        alts = node.get("alternateTitles") or []
        titles = [a.get("title", "") for a in alts]
        result["alternateTitles"] = ", ".join(titles) if titles else "-"

    if "latestDiaryEntry" in fields:
        diary = node.get("latestDiaryEntry")
        result["latestDiaryEntry"] = diary.get("title", "-") if diary else "-"

    # WikidotPage 标量字段
    for f in WIKIDOT_SCALARS:
        if f in fields:
            val = node.get(f)
            if val is None:
                result[f] = "-"
            elif isinstance(val, bool):
                result[f] = "Y" if val else "N"
            elif isinstance(val, list):
                result[f] = ", ".join(str(v) for v in val) if val else "-"
            else:
                result[f] = str(val)

    # 嵌套对象
    if "createdBy" in fields:
        cb = node.get("createdBy")
        result["createdBy"] = cb.get("displayName", "-") if cb else "-"

    if "parent" in fields:
        p = node.get("parent")
        result["parent"] = p.get("url", "-") if p else "-"

    if "children" in fields:
        ch = node.get("children") or []
        urls = [c.get("url", "") for c in ch]
        result["children"] = str(len(urls)) + " pages" if urls else "-"

    if "thread" in fields:
        th = node.get("thread")
        if th:
            result["thread"] = f"{th.get('title','')} ({th.get('postCount',0)} posts)"
        else:
            result["thread"] = "-"

    if "source" in fields:
        src = node.get("source", "")
        result["source"] = (src[:200] + "...") if len(src) > 200 else (src or "-")

    if "textContent" in fields:
        tc = node.get("textContent", "")
        result["textContent"] = (tc[:300] + "...") if len(tc) > 300 else (tc or "-")

    if "summary" in fields:
        sm = node.get("summary", "")
        result["summary"] = sm or "-"

    return result


def _format_page_results(edges: list, fields: list[str]) -> str:
    """将页面查询结果格式化为 Markdown。"""
    if not edges:
        return "(没有找到匹配的页面)"

    lines = []
    for i, edge in enumerate(edges):
        node = edge.get("node", {})
        data = _format_page_node(node, fields)

        lines.append(f"## 结果 {i + 1}")

        # 标题行
        title = data.get("title", "-")
        rating = data.get("rating", "-")
        url = data.get("url", "")
        lines.append(f"**{title}**  (评分: {rating})")
        lines.append(f"URL: {url}")

        # 按优先级排列关键字段
        key_fields = ["category", "createdAt", "voteCount", "createdBy", "attributions"]
        meta_parts = []
        for f in key_fields:
            if f in data and data[f] != "-":
                label = _field_label(f)
                meta_parts.append(f"{label}: {data[f]}")
        if meta_parts:
            lines.append(" | ".join(meta_parts))

        # 完整信息时展示更多字段
        if "tags" in data and data["tags"] not in ("-", ""):
            lines.append(f"标签: {data['tags']}")
        if "alternateTitles" in data and data["alternateTitles"] != "-":
            lines.append(f"替代标题: {data['alternateTitles']}")
        if "commentCount" in data and data["commentCount"] != "-":
            lines.append(f"评论数: {data['commentCount']} | 修订: {data.get('revisionCount','-')}")
        if "isHidden" in data:
            lines.append(f"隐藏: {data['isHidden']} | 用户页: {data.get('isUserPage','-')}")
        if "thread" in data and data["thread"] != "-":
            lines.append(f"论坛: {data['thread']}")
        if "parent" in data and data["parent"] != "-":
            lines.append(f"父页面: {data['parent']}")
        if "children" in data and data["children"] != "-":
            lines.append(f"子页面: {data['children']}")
        if "thumbnailUrl" in data and data["thumbnailUrl"] not in ("-", ""):
            lines.append(f"缩略图: {data['thumbnailUrl']}")
        if "summary" in data and data["summary"] != "-":
            lines.append(f"摘要: {data['summary']}")
        if "source" in data and data["source"] != "-":
            lines.append(f"源码: {data['source']}")
        if "textContent" in data and data["textContent"] != "-":
            lines.append(f"文本: {data['textContent']}")

        lines.append("")

    return "\n".join(lines)


def _field_label(f: str) -> str:
    """字段中文标签。"""
    labels = {
        "url": "URL", "title": "标题", "wikidotId": "Wikidot ID",
        "rating": "评分", "voteCount": "投票", "category": "分类",
        "tags": "标签", "createdAt": "创建时间", "revisionCount": "修订",
        "commentCount": "评论", "isHidden": "隐藏", "isUserPage": "用户页",
        "createdBy": "作者", "thumbnailUrl": "缩略图",
        "parent": "父页面", "children": "子页面", "thread": "论坛",
        "source": "源码", "textContent": "内容", "summary": "摘要",
        "attributions": "归属", "alternateTitles": "别名",
        "latestDiaryEntry": "日记",
    }
    return labels.get(f, f)


# ============================================================
# MCP 工具定义
# ============================================================

@mcp.tool(
    name="crom_search_pages",
    annotations={
        "title": "搜索 Crom 页面（按标题模糊匹配）",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_search_pages(params: CromSearchInput) -> str:
    """
    通过标题关键字搜索 Crom API 中的 Wikidot 页面。

    默认返回基本信息+作者（标题、评分、投票数、分类、创建时间、创建者、归属信息）。
    设置 detail_level='full' 可获得全部字段（含标签、源码、纯文本、论坛帖子、缩略图等）。

    支持模糊前缀匹配，同时搜索主标题和替代标题（alternateTitles）。
    """
    fields = _resolve_fields(params.detail_level)
    sort_key, sort_order = SORT_OPTIONS.get(
        params.sort, SORT_OPTIONS["rating_desc"]
    )
    site_url = SITE_PRESETS.get(params.site or "", None)

    # 构建筛选条件
    title_or_alt = f'''      _or: [
        {{
          onWikidotPage: {{
            title: {{ startsWithLower: "{params.title}" }}
          }}
        }}
        {{
          alternateTitles: {{
            title: {{ startsWithLower: "{params.title}" }}
          }}
        }}
      ]'''

    if site_url:
        filter_block = f'''      _and: [
        {{
          url: {{ startsWith: "{site_url}" }}
        }},
        {{
{title_or_alt}
        }}
      ]'''
    else:
        filter_block = title_or_alt

    fields_selection = _build_graphql_selection(fields)
    after_arg = f'\n    after: "{params.after}"' if params.after else ""

    query = f'''query CromSearch {{
  pages(
    filter: {{
{filter_block}
    }}
    sort: {{ key: {sort_key}, order: {sort_order} }}
    first: {params.limit}{after_arg}
  ) {{
    edges {{
      node {{
        url
{fields_selection}
      }}
      cursor
    }}
    pageInfo {{
      hasNextPage
      endCursor
    }}
  }}
}}'''

    try:
        result = await _gql_request(query)
    except RuntimeError as e:
        return f"查询失败: {e}"

    if "errors" in result:
        err_msgs = [e.get("message", str(e)) for e in result["errors"]]
        return f"GraphQL 错误: {'; '.join(err_msgs)}"

    data = result.get("data", {})
    pages = data.get("pages", {})
    edges = pages.get("edges", [])
    page_info = pages.get("pageInfo", {})

    if not edges:
        site_hint = f" (站点: {params.site})" if params.site else ""
        return f"未找到匹配 '{params.title}' 的页面{site_hint}。请尝试缩短关键字或更换站点。"

    level_label = "完整" if params.detail_level == DetailLevel.FULL else "基本信息+作者"
    lines = [
        f"# 搜索结果: '{params.title}'",
        f"匹配 {len(edges)} 条 | 模式: {level_label} | 排序: {params.sort}",
        f"hasNextPage: {page_info.get('hasNextPage', False)} | endCursor: {page_info.get('endCursor', 'N/A')}",
        "",
        _format_page_results(edges, fields),
        f"---",
        f"*如需查看完整信息（源码、摘要、论坛帖子等），请用 detail_level='full' 重新查询。*" if params.detail_level == DetailLevel.BASIC else "",
    ]
    return "\n".join(lines)


@mcp.tool(
    name="crom_get_page",
    annotations={
        "title": "获取指定 URL 的页面详情",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_get_page(params: CromGetPageInput) -> str:
    """
    通过 Wikidot 页面 URL 获取单个页面的详细信息。

    注意：Wikidot URL 始终使用 http://（非 https://），例如:
    'http://scp-wiki-cn.wikidot.com/scp-cn-001'
    """
    fields = _resolve_fields(params.detail_level)
    fields_selection = _build_graphql_selection(fields)

    query = f'''query CromGetPage {{
  page(url: "{params.url}") {{
    url
{fields_selection}
  }}
}}'''

    try:
        result = await _gql_request(query)
    except RuntimeError as e:
        return f"查询失败: {e}"

    if "errors" in result:
        err_msgs = [e.get("message", str(e)) for e in result["errors"]]
        return f"GraphQL 错误: {'; '.join(err_msgs)}"

    data = result.get("data", {})
    page = data.get("page")
    if not page:
        return f"未找到页面: {params.url}"

    # 用 _format_page_node 处理
    node_data = _format_page_node(page, fields)
    lines = [
        f"# {node_data.get('title', '-')}",
        f"URL: {node_data.get('url', '')}",
        f"评分: {node_data.get('rating', '-')} | 投票: {node_data.get('voteCount', '-')}",
        f"分类: {node_data.get('category', '-')} | 创建: {node_data.get('createdAt', '-')}",
        f"作者: {node_data.get('createdBy', '-')}",
        f"归属: {node_data.get('attributions', '-')}",
    ]

    if params.detail_level == DetailLevel.FULL:
        lines.append(f"标签: {node_data.get('tags', '-')}")
        lines.append(f"别名: {node_data.get('alternateTitles', '-')}")
        lines.append(f"评论数: {node_data.get('commentCount', '-')} | 修订: {node_data.get('revisionCount', '-')}")
        lines.append(f"论坛: {node_data.get('thread', '-')}")
        lines.append(f"摘要: {node_data.get('summary', '-')}")

    return "\n".join(lines)


@mcp.tool(
    name="crom_get_child_pages",
    annotations={
        "title": "获取页面的子页面列表",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_get_child_pages(params: CromGetChildPagesInput) -> str:
    """
    获取指定 Wikidot 页面的所有子页面（children pages）。

    子页面是 Wikidot 中通过 parent 字段指向当前页面的页面。
    常用于系列文章（如 SCP 系列、故事集、中心页等）的子集导航。

    默认返回基本信息+作者。设置 detail_level='full' 可获得全部字段。

    注意：Wikidot URL 必须使用 http:// 前缀。
    """
    fields = _resolve_fields(params.detail_level)
    child_fields = _build_graphql_selection(fields, base_indent=10)

    query = f'''query CromGetChildPages {{
  page(url: "{params.url}") {{
    url
    ... on WikidotPage {{
      title
      children {{
          url
{child_fields}
      }}
    }}
  }}
}}'''

    try:
        result = await _gql_request(query)
    except RuntimeError as e:
        return f"查询失败: {e}"

    if "errors" in result:
        err_msgs = [e.get("message", str(e)) for e in result["errors"]]
        return f"GraphQL 错误: {'; '.join(err_msgs)}"

    page = result.get("data", {}).get("page")
    if not page:
        return f"未找到页面: {params.url}"

    parent_title = page.get("title", "") or page.get("url", "未知页面")
    children = page.get("children") or []

    if not children:
        return (
            f"# 子页面: {parent_title}\n"
            f"父页面 URL: {params.url}\n\n"
            f"该页面没有子页面。\n\n"
            f"*提示: 某些页面类型（如非 WikidotPage）可能不支持子页面查询。*"
        )

    # 格式化每个子页面
    level_label = "完整" if params.detail_level == DetailLevel.FULL else "基本信息+作者"
    lines = [
        f"# 子页面列表: {parent_title}",
        f"父页面 URL: {params.url}",
        f"共 {len(children)} 个子页面 | 详情: {level_label}",
        "",
    ]

    for i, child in enumerate(children):
        data = _format_page_node(child, fields)
        title = data.get("title", "-")
        rating = data.get("rating", "-")
        url = data.get("url", "")
        category = data.get("category", "-")
        created = data.get("createdAt", "-")
        author = data.get("createdBy", "-")
        votes = data.get("voteCount", "-")

        lines.append(f"## {i + 1}. {title}")
        lines.append(f"URL: {url}")
        lines.append(f"评分: {rating} | 投票: {votes} | 分类: {category} | 创建: {created}")
        if author != "-":
            lines.append(f"作者: {author}")
        if data.get("attributions", "-") not in ("-", ""):
            lines.append(f"归属: {data['attributions']}")

        if params.detail_level == DetailLevel.FULL:
            if "tags" in data and data["tags"] not in ("-", ""):
                lines.append(f"标签: {data['tags']}")
            if "commentCount" in data:
                lines.append(f"评论: {data.get('commentCount', '-')} | 修订: {data.get('revisionCount', '-')}")
            if "alternateTitles" in data and data["alternateTitles"] != "-":
                lines.append(f"替代标题: {data['alternateTitles']}")
            if "thumbnailUrl" in data and data["thumbnailUrl"] not in ("-", ""):
                lines.append(f"缩略图: {data['thumbnailUrl']}")
            if "summary" in data and data["summary"] != "-":
                lines.append(f"摘要: {data['summary']}")

        lines.append("")

    lines.append("---")
    if params.detail_level == DetailLevel.BASIC:
        lines.append("*如需查看完整信息（标签、摘要等），请用 detail_level='full' 重新查询。*")

    return "\n".join(lines)


@mcp.tool(
    name="crom_get_forum_thread",
    annotations={
        "title": "获取 Wikidot 论坛帖子",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_get_forum_thread(params: CromThreadInput) -> str:
    """通过 thread ID 获取 Wikidot 论坛帖子详情。"""
    query = f'''query CromForumThread {{
  wikidotForumThread(threadId: "{params.thread_id}") {{
    threadId
    title
    description
    postCount
    createdAt
    createdBy {{
      displayName
      wikidotId
    }}
    site {{
      name
      url
    }}
  }}
}}'''

    try:
        result = await _gql_request(query)
    except RuntimeError as e:
        return f"查询失败: {e}"

    if "errors" in result:
        err_msgs = [e.get("message", str(e)) for e in result["errors"]]
        return f"GraphQL 错误: {'; '.join(err_msgs)}"

    thread = result.get("data", {}).get("wikidotForumThread")
    if not thread:
        return f"未找到论坛帖子: {params.thread_id}"

    site = thread.get("site") or {}
    created_by = thread.get("createdBy") or {}
    return "\n".join([
        f"# {thread.get('title', '-')}",
        f"Thread ID: {thread.get('threadId', '')}",
        f"帖子数: {thread.get('postCount', 0)} | 创建时间: {thread.get('createdAt', '-')}",
        f"作者: {created_by.get('displayName', '-')}",
        f"站点: {site.get('name', '-')} ({site.get('url', '-')})",
        f"",
        f"描述: {thread.get('description', '-')}",
    ])


@mcp.tool(
    name="crom_get_forum_post",
    annotations={
        "title": "获取 Wikidot 论坛回帖",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_get_forum_post(params: CromPostInput) -> str:
    """通过 post ID 获取 Wikidot 论坛回帖详情。"""
    query = f'''query CromForumPost {{
  wikidotForumPost(postId: "{params.post_id}") {{
    postId
    title
    content
    createdAt
    createdBy {{
      displayName
      wikidotId
    }}
    thread {{
      threadId
      title
    }}
    parentPost {{
      postId
    }}
  }}
}}'''

    try:
        result = await _gql_request(query)
    except RuntimeError as e:
        return f"查询失败: {e}"

    if "errors" in result:
        err_msgs = [e.get("message", str(e)) for e in result["errors"]]
        return f"GraphQL 错误: {'; '.join(err_msgs)}"

    post = result.get("data", {}).get("wikidotForumPost")
    if not post:
        return f"未找到论坛回帖: {params.post_id}"

    created_by = post.get("createdBy") or {}
    thread = post.get("thread") or {}
    content = post.get("content", "")
    if len(content) > 500:
        content = content[:500] + "..."

    return "\n".join([
        f"# {post.get('title', '-')}",
        f"Post ID: {post.get('postId', '')}",
        f"作者: {created_by.get('displayName', '-')}",
        f"所属帖子: {thread.get('title', '-')} ({thread.get('threadId', '')})",
        f"创建时间: {post.get('createdAt', '-')}",
        f"",
        f"内容:",
        content,
    ])


@mcp.tool(
    name="crom_list_sites",
    annotations={
        "title": "列出 Crom 支持的站点",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_list_sites() -> str:
    """返回 Crom API 支持的站点及其 URL 前缀列表。用于 crom_search_pages 的 site 参数参考。"""
    query = """query CromSites {
  sites {
    name
    url
    type
    platform
  }
}"""

    try:
        result = await _gql_request(query)
    except RuntimeError as e:
        # 网络查询失败时返回本地预设列表
        lines = ["# Crom 支持的站点（本地预设）", ""]
        for key, url in SITE_PRESETS.items():
            lines.append(f"- **{key}**: {url}")
        return "\n".join(lines)

    if "errors" in result:
        lines = ["# Crom 支持的站点（本地预设）", ""]
        for key, url in SITE_PRESETS.items():
            lines.append(f"- **{key}**: {url}")
        return "\n".join(lines)

    sites = result.get("data", {}).get("sites", [])
    lines = ["# Crom 支持的站点", ""]
    for site in sites:
        lines.append(f"- **{site.get('name', '?')}** ({site.get('type', '?')}/{site.get('platform', '?')})")
        lines.append(f"  URL: {site.get('url', '?')}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool(
    name="crom_get_page_source",
    annotations={
        "title": "获取页面正文/源码",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_get_page_source(params: CromPageSourceInput) -> str:
    """
    获取页面的 Wikidot 源码和/或纯文本内容。

    - source: Wikidot 标记语言源码（含 CSS 模块、include 指令等）
    - textContent: 提取后的纯文本（去除标记，适合阅读）

    注意：Wikidot URL 必须使用 http:// 前缀。
    查询消耗 1 rate limit point（source + textContent 各 1 点）。
    """
    # 按需构建字段
    fields_parts = []
    if params.content_type in (ContentType.SOURCE, ContentType.BOTH):
        fields_parts.append("    source")
    if params.content_type in (ContentType.TEXT, ContentType.BOTH):
        fields_parts.append("    textContent")

    fields_block = "\n".join(fields_parts)

    query = f'''query CromPageSource {{
  page(url: "{params.url}") {{
    url
    ... on WikidotPage {{
      title
{fields_block}
    }}
  }}
}}'''

    try:
        result = await _gql_request(query)
    except RuntimeError as e:
        return f"查询失败: {e}"

    if "errors" in result:
        err_msgs = [e.get("message", str(e)) for e in result["errors"]]
        return f"GraphQL 错误: {'; '.join(err_msgs)}"

    page = result.get("data", {}).get("page")
    if not page:
        return f"未找到页面: {params.url}"

    title = page.get("title", "") or page.get("url", "未知页面")
    lines = [f"# {title}", f"URL: {page.get('url', '')}", ""]

    # source 和 textContent 也在 ... on WikidotPage fragment 中
    source = page.get("source", "")
    text_content = page.get("textContent", "")

    if params.content_type in (ContentType.SOURCE, ContentType.BOTH):
        lines.append("## Wikidot 源码 (source)")
        lines.append("```")
        lines.append(source if source else "(无源码)")
        lines.append("```")
        lines.append("")

    if params.content_type in (ContentType.TEXT, ContentType.BOTH):
        lines.append("## 纯文本内容 (textContent)")
        lines.append("```")
        lines.append(text_content if text_content else "(无文本内容)")
        lines.append("```")
        lines.append("")

    # 统计信息
    if source:
        lines.append(f"源码长度: {len(source)} 字符")
    if text_content:
        lines.append(f"纯文本长度: {len(text_content)} 字符")

    return "\n".join(lines)


@mcp.tool(
    name="crom_get_user",
    annotations={
        "title": "查询 Wikidot 用户信息",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_get_user(params: CromGetUserInput) -> str:
    """
    通过用户名（displayName）查询 Wikidot 用户的基本信息。

    返回用户 ID、用户名等基本信息。如需查询该作者的页面，请使用 crom_search_by_author 工具。
    """
    query = f'''query CromGetUser {{
  wikidotUser(displayName: "{params.user_name}") {{
    displayName
    wikidotId
  }}
}}'''

    try:
        result = await _gql_request(query)
    except RuntimeError as e:
        return f"查询失败: {e}"

    if "errors" in result:
        err_msgs = [e.get("message", str(e)) for e in result["errors"]]
        return f"GraphQL 错误: {'; '.join(err_msgs)}"

    user = result.get("data", {}).get("wikidotUser")
    if not user:
        return f"未找到用户: {params.user_name}\n请检查用户名拼写（注意大小写不敏感，但需精确匹配）。"

    return "\n".join([
        f"# 用户信息: {user.get('displayName', '-')}",
        f"",
        f"- **用户名**: {user.get('displayName', '-')}",
        f"- **Wikidot ID**: {user.get('wikidotId', '-')}",
        f"",
        f"*提示: 使用 crom_search_by_author 工具可查询该用户的页面列表。*",
    ])


@mcp.tool(
    name="crom_search_by_tag",
    annotations={
        "title": "按标签搜索 Wikidot 页面",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_search_by_tag(params: CromSearchByTagInput) -> str:
    """
    按标签（tag）搜索 Crom API 中的 Wikidot 页面。

    标签是 Wikidot 页面的分类标记，如 'scp'、'keter'、'safe'、'euclid'、'joke'、'goi-format' 等。
    支持大小写不敏感的精确匹配，可限定站点范围。

    默认返回基本信息+作者。设置 detail_level='full' 可获得全部字段。
    """
    fields = _resolve_fields(params.detail_level)
    sort_key, sort_order = SORT_OPTIONS.get(
        params.sort, SORT_OPTIONS["rating_desc"]
    )
    site_url = SITE_PRESETS.get(params.site or "", None)
    fields_selection = _build_graphql_selection(fields)
    after_arg = f'\n    after: "{params.after}"' if params.after else ""

    # 构建 onWikidotPage 筛选条件
    on_wikidot_filters = f'          tags: {{ eq: "{params.tag}" }}'

    if site_url:
        on_wikidot_filters += f'\n          url: {{ startsWith: "{site_url}" }}'

    query = f'''query CromSearchByTag {{
  pages(
    filter: {{
      onWikidotPage: {{
{on_wikidot_filters}
      }}
    }}
    sort: {{ key: {sort_key}, order: {sort_order} }}
    first: {params.limit}{after_arg}
  ) {{
    edges {{
      node {{
        url
{fields_selection}
      }}
      cursor
    }}
    pageInfo {{
      hasNextPage
      endCursor
    }}
  }}
}}'''

    try:
        result = await _gql_request(query)
    except RuntimeError as e:
        return f"查询失败: {e}"

    if "errors" in result:
        err_msgs = [e.get("message", str(e)) for e in result["errors"]]
        return f"GraphQL 错误: {'; '.join(err_msgs)}"

    data = result.get("data", {})
    pages = data.get("pages", {})
    edges = pages.get("edges", [])
    page_info = pages.get("pageInfo", {})

    if not edges:
        site_hint = f" (站点: {params.site})" if params.site else ""
        return f"未找到标签为 '{params.tag}' 的页面{site_hint}。请检查标签拼写或尝试更换站点。"

    level_label = "完整" if params.detail_level == DetailLevel.FULL else "基本信息+作者"
    lines = [
        f"# 标签搜索: '{params.tag}'",
        f"匹配 {len(edges)} 条 | 模式: {level_label} | 排序: {params.sort}",
        f"hasNextPage: {page_info.get('hasNextPage', False)} | endCursor: {page_info.get('endCursor', 'N/A')}",
        "",
        _format_page_results(edges, fields),
        f"---",
        f"*如需查看完整信息（源码、摘要、论坛帖子等），请用 detail_level='full' 重新查询。*" if params.detail_level == DetailLevel.BASIC else "",
    ]
    return "\n".join(lines)


@mcp.tool(
    name="crom_search_by_author",
    annotations={
        "title": "按作者/归属/发布者搜索 Wikidot 页面",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_search_by_author(params: CromSearchByAuthorInput) -> str:
    """
    按作者归属信息（attributions）搜索 Wikidot 页面。

    支持按作者（AUTHOR）、译者（TRANSLATOR）、改写者（REWRITE）或全部类型（ALL）筛选。
    通过大小写不敏感的精确匹配查找用户的归属页面。

    默认返回基本信息+作者。设置 detail_level='full' 可获得全部字段。
    """
    fields = _resolve_fields(params.detail_level)
    sort_key, sort_order = SORT_OPTIONS.get(
        params.sort, SORT_OPTIONS["rating_desc"]
    )
    site_url = SITE_PRESETS.get(params.site or "", None)
    fields_selection = _build_graphql_selection(fields)
    after_arg = f'\n    after: "{params.after}"' if params.after else ""

    # 构建 filter 条件 — 仅 attribution 模式
    # (createdBy 不是 WikidotPageQueryFilter 的可筛选字段)
    if params.attribution_type == AttributionType.ALL:
        # ALL: 用 _and 包裹 _or(type) 和 user 条件
        attr_content = f"""        _and: [
          {{
            _or: [
              {{ type: {{ eq: AUTHOR }} }}
              {{ type: {{ eq: TRANSLATOR }} }}
              {{ type: {{ eq: REWRITE }} }}
            ]
          }},
          {{
            user: {{ displayName: {{ eqLower: "{params.author_name}" }} }}
          }}
        ]"""
    else:
        # 单一类型：type + user 直接并列（默认 AND）
        attr_content = f"""        type: {{ eq: {params.attribution_type.value} }}
        user: {{ displayName: {{ eqLower: "{params.author_name}" }} }}"""

    attr_block = f"""      attributions: {{
{attr_content}
      }}"""

    if site_url:
        filter_block = f"""{attr_block}
      onWikidotPage: {{
        url: {{ startsWith: "{site_url}" }}
      }}"""
    else:
        filter_block = attr_block

    query = f'''query CromSearchByAuthor {{
  pages(
    filter: {{
{filter_block}
    }}
    sort: {{ key: {sort_key}, order: {sort_order} }}
    first: {params.limit}{after_arg}
  ) {{
    edges {{
      node {{
        url
{fields_selection}
      }}
      cursor
    }}
    pageInfo {{
      hasNextPage
      endCursor
    }}
  }}
}}'''

    try:
        result = await _gql_request(query)
    except RuntimeError as e:
        return f"查询失败: {e}"

    if "errors" in result:
        err_msgs = [e.get("message", str(e)) for e in result["errors"]]
        return f"GraphQL 错误: {'; '.join(err_msgs)}"

    data = result.get("data", {})
    pages = data.get("pages", {})
    edges = pages.get("edges", [])
    page_info = pages.get("pageInfo", {})

    if not edges:
        site_hint = f" (站点: {params.site})" if params.site else ""
        return (
            f"未找到归属用户为 '{params.author_name}' 的页面{site_hint}。\n"
            f"提示: 尝试调整 attribution_type（当前: {params.attribution_type.value}），"
            f"或检查用户名拼写。"
        )

    level_label = "完整" if params.detail_level == DetailLevel.FULL else "基本信息+作者"
    lines = [
        f"# 作者搜索: '{params.author_name}'",
        f"匹配 {len(edges)} 条 | 类型: {params.attribution_type.value} | 排序: {params.sort} | 详情: {level_label}",
        f"hasNextPage: {page_info.get('hasNextPage', False)} | endCursor: {page_info.get('endCursor', 'N/A')}",
        "",
        _format_page_results(edges, fields),
        f"---",
        f"*如需查看完整信息，请用 detail_level='full' 重新查询。*" if params.detail_level == DetailLevel.BASIC else "",
    ]
    return "\n".join(lines)


# ============================================================
# 统一搜索辅助函数
# ============================================================

def _validate_search_criteria(title, author_name, tags):
    """校验至少提供了一个搜索条件。"""
    if not title and not author_name and not (tags and len(tags) > 0):
        raise ValueError("至少需要提供 title、author_name 或 tags 中的一个搜索条件")


def _build_unified_filter(title, author_name, attribution_type, tags, site_url):
    """构建统一搜索的组合 Filter 字符串。

    所有条件用 _and 包裹在 PageQueryFilter 顶层，每个条件都是独立的 PageQueryFilter。
    """
    conditions = []

    # 1. 标题过滤（模糊前缀匹配，同时搜索主标题 + 替代标题）
    if title:
        title_cond = f'''          {{
            _or: [
              {{ onWikidotPage: {{ title: {{ startsWithLower: "{title}" }} }} }}
              {{ alternateTitles: {{ title: {{ startsWithLower: "{title}" }} }} }}
            ]
          }}'''
        conditions.append(title_cond)

    # 2. 作者归属过滤
    if author_name:
        if attribution_type == AttributionType.ALL:
            attr_cond = f'''          {{
            attributions: {{
              _and: [
                {{
                  _or: [
                    {{ type: {{ eq: AUTHOR }} }}
                    {{ type: {{ eq: TRANSLATOR }} }}
                    {{ type: {{ eq: REWRITE }} }}
                  ]
                }},
                {{ user: {{ displayName: {{ eqLower: "{author_name}" }} }} }}
              ]
            }}
          }}'''
        else:
            attr_cond = f'''          {{
            attributions: {{
              type: {{ eq: {attribution_type.value} }}
              user: {{ displayName: {{ eqLower: "{author_name}" }} }}
            }}
          }}'''
        conditions.append(attr_cond)

    # 3. 标签过滤（每个标签一个独立 PageQueryFilter，AND 关系）
    if tags:
        for t in tags:
            t = t.strip()
            if t:
                tag_cond = f'          {{ onWikidotPage: {{ tags: {{ eq: "{t}" }} }} }}'
                conditions.append(tag_cond)

    # 4. 站点过滤
    if site_url:
        site_cond = f'          {{ url: {{ startsWith: "{site_url}" }} }}'
        conditions.append(site_cond)

    # 用 _and 包裹所有条件（即使只有一个条件也用 _and，保持一致性）
    body = ",\n".join(conditions)
    return f"      _and: [\n{body}\n      ]"


# ============================================================
# 统一搜索入口
# ============================================================

@mcp.tool(
    name="crom_search",
    annotations={
        "title": "统一搜索 Wikidot 页面（支持组合条件）",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_search(params: CromUnifiedSearchInput) -> str:
    """
    统一搜索 Crom API 中的 Wikidot 页面，支持任意组合过滤条件。

    所有提供的条件之间为 AND 关系（同时满足）。例如:
    - author_name='W Asriel' + tags=['scp', 'keter'] → 查找 W Asriel 参与且同时含有 scp 和 keter 标签的页面
    - title='SCP-001' + site='scp-cn' → 在 SCP-CN 站内搜索标题以 SCP-001 开头的页面
    - tags=['joke'] → 查找所有含有 joke 标签的页面

    默认返回基本信息+作者。设置 detail_level='full' 可获得全部字段。
    """
    # 校验输入
    try:
        _validate_search_criteria(params.title, params.author_name, params.tags)
    except ValueError as e:
        return f"参数错误: {e}"

    fields = _resolve_fields(params.detail_level)
    sort_key, sort_order = SORT_OPTIONS.get(
        params.sort, SORT_OPTIONS["rating_desc"]
    )
    site_url = SITE_PRESETS.get(params.site or "", None)
    fields_selection = _build_graphql_selection(fields)
    after_arg = f'\n    after: "{params.after}"' if params.after else ""

    filter_block = _build_unified_filter(
        title=params.title,
        author_name=params.author_name,
        attribution_type=params.attribution_type,
        tags=params.tags,
        site_url=site_url,
    )

    query = f'''query CromUnifiedSearch {{
  pages(
    filter: {{
{filter_block}
    }}
    sort: {{ key: {sort_key}, order: {sort_order} }}
    first: {params.limit}{after_arg}
  ) {{
    edges {{
      node {{
        url
{fields_selection}
      }}
      cursor
    }}
    pageInfo {{
      hasNextPage
      endCursor
    }}
  }}
}}'''

    try:
        result = await _gql_request(query)
    except RuntimeError as e:
        return f"查询失败: {e}"

    if "errors" in result:
        err_msgs = [e.get("message", str(e)) for e in result["errors"]]
        return f"GraphQL 错误: {'; '.join(err_msgs)}"

    data = result.get("data", {})
    pages = data.get("pages", {})
    edges = pages.get("edges", [])
    page_info = pages.get("pageInfo", {})

    if not edges:
        parts = []
        if params.title:
            parts.append(f"标题 '{params.title}'")
        if params.author_name:
            parts.append(f"作者 '{params.author_name}' ({params.attribution_type.value})")
        if params.tags:
            parts.append(f"标签 {params.tags}")
        site_hint = f" (站点: {params.site})" if params.site else ""
        return f"未找到匹配页面{site_hint}。\n条件: {' + '.join(parts)}\n请尝试放宽条件或检查拼写。"

    # 构建描述标签
    filters_desc = []
    if params.title:
        filters_desc.append(f"标题: {params.title}")
    if params.author_name:
        filters_desc.append(f"作者: {params.author_name} ({params.attribution_type.value})")
    if params.tags:
        filters_desc.append(f"标签: {', '.join(params.tags)}")
    if params.site:
        filters_desc.append(f"站点: {params.site}")

    level_label = "完整" if params.detail_level == DetailLevel.FULL else "基本信息+作者"
    lines = [
        f"# 统一搜索",
        f"条件: {' | '.join(filters_desc)}",
        f"匹配 {len(edges)} 条 | 详情: {level_label} | 排序: {params.sort}",
        f"hasNextPage: {page_info.get('hasNextPage', False)} | endCursor: {page_info.get('endCursor', 'N/A')}",
        "",
        _format_page_results(edges, fields),
        f"---",
        f"*如需查看完整信息（源码、摘要、论坛帖子等），请用 detail_level='full' 重新查询。*" if params.detail_level == DetailLevel.BASIC else "",
    ]
    return "\n".join(lines)


@mcp.tool(
    name="crom_get_author_stats",
    annotations={
        "title": "查询作者统计数据（排名、评分、页数等）",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_get_author_stats(params: CromAuthorStatsInput) -> str:
    """
    查询指定作者的详细统计数据。

    通过 wikidotUser 查询作者的全站排名、总评分、平均评分、
    各类型页面数量（SCP/Tale/GoiFormat/Artwork）等统计信息。

    消耗 1 rate limit point。
    """
    # 通过 wikidotUser 查询统计数据
    query = f'''query AuthorStats {{
  wikidotUser(displayName: "{params.author_name}") {{
    displayName
    wikidotId
    unixName
    statistics {{
      rank
      totalRating
      meanRating
      pageCount
      pageCountScp
      pageCountTale
      pageCountGoiFormat
      pageCountArtwork
    }}
  }}
}}'''

    try:
        result = await _gql_request(query)
    except RuntimeError as e:
        return f"查询失败: {e}"

    if "errors" in result:
        err_msgs = [e.get("message", str(e)) for e in result["errors"]]
        return f"GraphQL 错误: {'; '.join(err_msgs)}"

    user = result.get("data", {}).get("wikidotUser")
    if not user:
        return (
            f"未找到作者: {params.author_name}\n"
            f"请检查用户名拼写（大小写不敏感，但需精确匹配）。"
        )

    stats = user.get("statistics") or {}

    # 计算各类页面的占比
    total = stats.get("pageCount", 0)
    def pct(n):
        return f"{n / total * 100:.1f}%" if total > 0 and n else "-"

    lines = [
        f"# 作者统计: {user.get('displayName', '-')}",
        "",
        f"## 基本信息",
        f"- **用户名**: {user.get('displayName', '-')}",
        f"- **Wikidot ID**: {user.get('wikidotId', '-')}",
        f"- **Unix 名**: {user.get('unixName', '-')}",
        "",
        f"## 排名与评分",
        f"- **全站排名**: #{stats.get('rank', '?')}",
        f"- **总评分**: {stats.get('totalRating', '?')}",
        f"- **平均评分**: {stats.get('meanRating', '?')}",
        "",
        f"## 页面创作统计",
        f"- **总页数**: {total}",
        f"  - SCP 文档: {stats.get('pageCountScp', '?')} ({pct(stats.get('pageCountScp', 0))})",
        f"  - Tale: {stats.get('pageCountTale', '?')} ({pct(stats.get('pageCountTale', 0))})",
        f"  - GoI 格式: {stats.get('pageCountGoiFormat', '?')} ({pct(stats.get('pageCountGoiFormat', 0))})",
        f"  - 艺术作品: {stats.get('pageCountArtwork', '?')} ({pct(stats.get('pageCountArtwork', 0))})",
        "",
        f"---",
        f"*提示: 使用 crom_search_by_author 可查询该作者的页面列表。*",
    ]
    return "\n".join(lines)


@mcp.tool(
    name="crom_get_top_authors",
    annotations={
        "title": "查询作者排行榜（按总评分排名）",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def crom_get_top_authors(params: CromTopAuthorsInput) -> str:
    """
    通过排名（rank）反查作者及其统计数据。

    使用 usersByRank_v1 按排名区间批量查询作者，返回每位作者的排名、总评分、
    平均评分、各类型页面数量（SCP/Tale/GoI/Artwork）等。

    每查询一位作者消耗 2 rate limit points（共 limit × 2 pts）。
    例如查询 Top 10 消耗 20 pts。
    """
    import asyncio

    site_url = SITE_PRESETS.get(params.site or "", None)
    site_arg = f', siteUrl: "{site_url}"' if site_url else ""

    async def _fetch_one(rank: int) -> dict | None:
        query = f"""query RankAuthor {{
  usersByRank_v1(rank: {rank}{site_arg}) {{
    displayName
    statistics {{
      rank
      totalRating
      meanRating
      pageCount
      pageCountScp
      pageCountTale
      pageCountGoiFormat
      pageCountArtwork
    }}
  }}
}}"""
        try:
            result = await _gql_request(query)
            if "errors" in result:
                logger.warning(f"Rank #{rank}: {result['errors'][0]['message'][:120]}")
                return None
            users = result.get("data", {}).get("usersByRank_v1", [])
            return users[0] if users else None
        except RuntimeError as e:
            logger.warning(f"Rank #{rank} timeout: {e}")
            return None

    ranks = list(range(params.start_rank, params.start_rank + params.limit))
    results = await asyncio.gather(*[_fetch_one(r) for r in ranks])

    authors = [r for r in results if r is not None and r.get("displayName")]

    if not authors:
        site_hint = f" (站点: {params.site})" if params.site else ""
        return f"未能获取排名 {params.start_rank}-{params.start_rank + params.limit - 1} 的作者数据{site_hint}。\n可能原因: 网络超时或被限流（本查询消耗 {len(ranks) * 2} pts）。"

    site_label = f" @ {params.site}" if params.site else " (全站)"
    lines = [
        f"# 作者排行榜{site_label}",
        f"排名 {params.start_rank}-{params.start_rank + len(authors) - 1} | 查询 {len(ranks)} 位 | 消耗 {len(ranks) * 2} pts",
        "",
        "| 排名 | 作者 | 总评分 | 均分 | 总页数 | SCP | Tale | GoI | 艺术 |",
        "|:----:|------|-------:|-----:|-------:|----:|-----:|----:|-----:|",
    ]

    for author in authors:
        s = author.get("statistics") or {}
        display = author.get("displayName", "?")
        row = (
            f"| {s.get('rank', '?')} "
            f"| {display} "
            f"| {s.get('totalRating', '?')} "
            f"| {s.get('meanRating', '?')} "
            f"| {s.get('pageCount', '?')} "
            f"| {s.get('pageCountScp', '?')} "
            f"| {s.get('pageCountTale', '?')} "
            f"| {s.get('pageCountGoiFormat', '?')} "
            f"| {s.get('pageCountArtwork', '?')} |"
        )
        lines.append(row)

    lines.append("")
    lines.append(f"*提示: 使用 crom_get_author_stats 可查看单个作者的详细统计数据。*")
    return "\n".join(lines)


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    mcp.run()
