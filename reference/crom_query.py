#!/usr/bin/env python3
"""
Crom API v2 查询工具
-------------------
支持交互式选择字段、按标题模糊查询、分页浏览结果。
Endpoint: https://apiv2.crom.avn.sh/graphql
"""

import json
import urllib.request
import urllib.error
import ssl
import sys
import os
from typing import Optional

ENDPOINT = "https://apiv2.crom.avn.sh/graphql"

# 解决 Windows GBK 编码和 SSL 证书问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 创建不验证证书的 SSL 上下文（解决 Windows 下缺少 CA 证书的问题）
SSL_CONTEXT = ssl.create_default_context()
try:
    SSL_CONTEXT  # 尝试用默认上下文
except Exception:
    SSL_CONTEXT = ssl._create_unverified_context()

# ============================================================
# 可用字段定义
# ============================================================
INTERFACE_FIELDS = {
    "url":               "页面 URL",
    "alternateTitles":   "替代标题列表",
    "attributions":      "作者/译者/改写者归属信息",
    "inDefaultReadingList": "是否在默认阅读列表中",
    "latestDiaryEntry":  "最新日记条目",
}

WIKIDOT_FIELDS = {
    "title":             "页面标题",
    "wikidotId":         "Wikidot 内部 ID",
    "rating":            "评分",
    "voteCount":         "投票数",
    "category":          "分类",
    "tags":              "标签",
    "createdAt":         "创建时间",
    "revisionCount":     "修订次数",
    "commentCount":      "评论数",
    "isHidden":          "是否隐藏",
    "isUserPage":        "是否为用户页",
    "createdBy":         "创建者",
    "thumbnailUrl":      "缩略图 URL",
    "parent":            "父页面",
    "children":          "子页面列表",
    "thread":            "关联论坛帖子",
    "source":            "Wikidot 页面源码",
    "textContent":       "纯文本内容",
    "summary":           "页面摘要",
}

# 预设字段组
PRESETS = {
    "1": {
        "name": "基本信息",
        "fields": ["title", "rating", "voteCount", "category", "createdAt"],
    },
    "2": {
        "name": "基本信息 + 作者",
        "fields": ["title", "rating", "voteCount", "category", "createdAt", "createdBy", "attributions"],
    },
    "3": {
        "name": "完整信息",
        "fields": list(WIKIDOT_FIELDS.keys()) + ["attributions", "alternateTitles"],
    },
    "4": {
        "name": "自定义选择",
        "fields": None,  # 触发手动选择
    },
}

SITE_PRESETS = {
    "1": ("SCP-CN",    "http://scp-wiki-cn.wikidot.com/"),
    "2": ("SCP-EN",    "http://scp-wiki.wikidot.com/"),
    "3": ("SCP-INT",   "http://scp-int.wikidot.com/"),
    "4": ("SCP-RU",    "http://scp-ru.wikidot.com/"),
    "5": ("SCP-FR",    "http://fondationscp.wikidot.com/"),
    "6": ("Wanderer's Library", "http://wanderers-library.wikidot.com/"),
    "7": ("Backrooms", "http://backrooms-wiki.wikidot.com/"),
    "8": ("所有站点（不限）", None),
}

SORT_OPTIONS = {
    "1": ("评分降序", "WIKIDOT_RATING", "DESC"),
    "2": ("评分升序", "WIKIDOT_RATING", "ASC"),
    "3": ("创建时间降序", "WIKIDOT_CREATED_AT", "DESC"),
    "4": ("创建时间升序", "WIKIDOT_CREATED_AT", "ASC"),
    "5": ("标题升序", "WIKIDOT_TITLE", "ASC"),
    "6": ("最新归属日期降序", "LATEST_ATTRIBUTION_DATE", "DESC"),
}


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def gql_request(query: str, variables: dict = None) -> dict:
    """发送 GraphQL 请求并返回 JSON 响应。"""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ssl.SSLError) as ssl_err:
        # SSL 回退：使用不验证证书的方式
        unverified_ctx = ssl._create_unverified_context()
        try:
            req2 = urllib.request.Request(
                ENDPOINT,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req2, timeout=30, context=unverified_ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code}: {body}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"网络错误: {e.reason}")


def build_fields_selection(fields: list[str]) -> str:
    """根据选中的字段列表构建 GraphQL 字段片段。"""
    parts = []

    # ---- 接口通用字段（直接放在 node 下）----
    interface_fields = []
    for f in fields:
        if f == "url":
            continue  # url 在 query 模板中固定输出
        if f in INTERFACE_FIELDS and f not in ("attributions", "alternateTitles", "latestDiaryEntry"):
            interface_fields.append(f"        {f}")

    if interface_fields:
        parts.append("\n".join(interface_fields))

    # 接口上的嵌套字段（直接放在 node 下，因为所有 ResolvedPage 实现都有）
    if "attributions" in fields:
        parts.append("""        attributions {
          type
          user {
            ... on WikidotUser {
              displayName
              wikidotId
            }
          }
        }""")

    if "alternateTitles" in fields:
        parts.append("""        alternateTitles {
          title
        }""")

    if "latestDiaryEntry" in fields:
        parts.append("""        latestDiaryEntry {
          id
          title
          createdAt
        }""")

    if "inDefaultReadingList" in fields and "inDefaultReadingList" not in [f for f in interface_fields]:
        parts.append("        inDefaultReadingList")

    # ---- 所有 WikidotPage 特化字段合并到单个 inline fragment ----
    wikidot_scalars = [
        "title", "wikidotId", "rating", "voteCount", "category",
        "tags", "createdAt", "revisionCount", "commentCount",
        "isHidden", "isUserPage", "thumbnailUrl", "source", "textContent", "summary",
    ]
    wikidot_scalar_lines = [f"          {f}" for f in fields if f in wikidot_scalars]

    wikidot_fragment_body = []

    # 标量字段
    if wikidot_scalar_lines:
        wikidot_fragment_body.extend(wikidot_scalar_lines)

    # 嵌套对象字段
    if "createdBy" in fields:
        wikidot_fragment_body.append("""          createdBy {
            displayName
            wikidotId
          }""")

    if "parent" in fields:
        wikidot_fragment_body.append("""          parent {
            url
          }""")

    if "children" in fields:
        wikidot_fragment_body.append("""          children {
            url
          }""")

    if "thread" in fields:
        wikidot_fragment_body.append("""          thread {
            threadId
            title
            postCount
            createdAt
          }""")

    if wikidot_fragment_body:
        body = "\n".join(wikidot_fragment_body)
        parts.append(f"""        ... on WikidotPage {{
{body}
        }}""")

    return "\n".join(parts)


def build_query(title_filter: str, site_url: Optional[str], fields: list[str],
                sort_key: str, sort_order: str, first: int, after: Optional[str] = None) -> str:
    """构建完整的 GraphQL 查询字符串。"""
    # 构建 filter 部分

    # 标题搜索：同时匹配主标题和 alternateTitles
    title_or_alt = f'''      _or: [
        {{
          onWikidotPage: {{
            title: {{ startsWithLower: "{title_filter}" }}
          }}
        }}
        {{
          alternateTitles: {{
            title: {{ startsWithLower: "{title_filter}" }}
          }}
        }}
      ]'''

    if site_url:
        # 有站点限制时，用 _and 组合站点过滤和标题搜索
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

    # 构建 fields 部分
    fields_block = build_fields_selection(fields)

    # after 参数
    after_arg = f'\n    after: "{after}"' if after else ""

    query = f'''query CromSearch {{
  pages(
    filter: {{
{filter_block}
    }}
    sort: {{ key: {sort_key}, order: {sort_order} }}
    first: {first}{after_arg}
  ) {{
    edges {{
      node {{
        url{fields_block}
      }}
      cursor
    }}
    pageInfo {{
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
    }}
  }}
}}'''
    return query


def format_value(val) -> str:
    """格式化单个值用于显示。"""
    if val is None:
        return "-"
    if isinstance(val, bool):
        return "[Y]" if val else "[N]"
    if isinstance(val, list):
        if not val:
            return "-"
        if isinstance(val[0], str):
            return ", ".join(val)
        if isinstance(val[0], dict) and "displayName" in val[0]:
            return ", ".join(v.get("displayName", "?") for v in val)
        if isinstance(val[0], dict) and "title" in val[0]:
            return ", ".join(v.get("title", "?") for v in val)
        if isinstance(val[0], dict) and "type" in val[0] and "user" in val[0]:
            parts = []
            for a in val:
                user = a.get("user", {})
                name = user.get("displayName", "?") if user else "?"
                parts.append(f"{name}[{a.get('type','?')}]")
            return ", ".join(parts)
        return str(len(val)) + " items"
    if isinstance(val, dict):
        if "displayName" in val:
            return val["displayName"]
        if "title" in val and "postCount" in val:
            # WikidotForumThread
            return f"{val['title']} ({val.get('postCount',0)}帖)"
        if "title" in val:
            return val["title"]
        if "url" in val:
            return val["url"]
        if "threadId" in val:
            return val["threadId"]
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def truncate(s: str, width: int) -> str:
    """截断字符串到指定宽度。"""
    if len(s) <= width:
        return s.ljust(width)
    return s[:width - 2] + ".."


def display_results(result: dict, fields: list[str], page_size: int):
    """以表格形式展示查询结果。"""
    data = result.get("data", {})
    pages = data.get("pages", {})
    edges = pages.get("edges", [])
    page_info = pages.get("pageInfo", {})

    if not edges:
        print("\n  (没有找到匹配的页面)\n")
        return

    # 需要显示的列：url + 选中的字段（扁平化）
    display_fields = ["url"] + [f for f in fields if f != "url"]
    # 扁平化 nested 字段
    flat_fields = []
    for f in display_fields:
        if f in ("attributions", "alternateTitles", "createdBy",
                  "parent", "children", "thread"):
            flat_fields.append(f)
        else:
            flat_fields.append(f)

    # 计算列宽
    col_widths = {}
    for f in flat_fields:
        col_widths[f] = min(len(FIELD_LABELS.get(f, f)), 20)

    rows = []
    for edge in edges:
        node = edge.get("node", {})
        row = {}
        for f in flat_fields:
            # 从 node 或 node 的 wikidot fragment 中取值
            val = node.get(f)
            # 某些字段在 ... on WikidotPage fragment 里
            if val is None:
                val = node.get(f, "-")
            display = format_value(val)
            col_widths[f] = max(col_widths[f], min(len(display), 40))
            row[f] = display
        rows.append(row)

    # 打印表头
    header = "  " + " | ".join(
        truncate(FIELD_LABELS.get(f, f), col_widths[f]) for f in flat_fields
    )
    sep = "  " + "-+-".join("-" * col_widths[f] for f in flat_fields)
    print(f"\n{header}")
    print(sep)

    for i, row in enumerate(rows):
        line = "  " + " | ".join(
            truncate(row[f], col_widths[f]) for f in flat_fields
        )
        print(line)

    print(f"\n  第 1-{len(edges)} 条")
    print(f"  hasNextPage: {page_info.get('hasNextPage', False)}"
          f"  |  hasPreviousPage: {page_info.get('hasPreviousPage', False)}")
    return page_info


# 字段标签映射（用于表头）
FIELD_LABELS = {
    "url": "URL",
    "title": "标题",
    "wikidotId": "Wikidot ID",
    "rating": "评分",
    "voteCount": "投票数",
    "category": "分类",
    "tags": "标签",
    "createdAt": "创建时间",
    "revisionCount": "修订次数",
    "commentCount": "评论数",
    "isHidden": "隐藏",
    "isUserPage": "用户页",
    "createdBy": "创建者",
    "thumbnailUrl": "缩略图",
    "parent": "父页面",
    "children": "子页面",
    "attributions": "归属信息",
    "alternateTitles": "替代标题",
    "inDefaultReadingList": "默认阅读列表",
    "latestDiaryEntry": "最新日记",
    "source": "源码",
    "textContent": "文本内容",
    "summary": "摘要",
    "thread": "论坛帖子",
}


def select_fields_interactively() -> list[str]:
    """交互式字段选择。"""
    print("\n  可用字段：\n")
    all_fields = []
    idx = 1
    mapping = {}

    print("  -- 通用字段 --")
    for key, desc in INTERFACE_FIELDS.items():
        if key == "url":
            continue  # url 始终包含
        print(f"  [{idx:2d}] {key:<25s} {desc}")
        mapping[str(idx)] = key
        all_fields.append(key)
        idx += 1

    print("\n  -- WikidotPage 特化字段 --")
    for key, desc in WIKIDOT_FIELDS.items():
        print(f"  [{idx:2d}] {key:<25s} {desc}")
        mapping[str(idx)] = key
        all_fields.append(key)
        idx += 1

    print(f"\n  输入字段编号（多个用逗号分隔，如 1,3,5,7），按回车使用默认（基本信息）")
    choice = input("  > ").strip()

    if not choice:
        return PRESETS["1"]["fields"] + ["url"]

    selected = []
    for part in choice.split(","):
        part = part.strip()
        if part in mapping:
            selected.append(mapping[part])
        elif part.isdigit() and 0 < int(part) <= len(all_fields):
            # fallback to index
            selected.append(all_fields[int(part) - 1])

    if not selected:
        print("  未选中任何字段，使用默认。")
        return PRESETS["1"]["fields"] + ["url"]

    # url 始终包含
    if "url" not in selected:
        selected.insert(0, "url")

    return selected


def main():
    clear_screen()
    print("=" * 60)
    print("  Crom API v2 - 页面查询工具")
    print("  https://apiv2.crom.avn.sh/graphql")
    print("=" * 60)

    # ---- 步骤 1: 输入标题关键字 ----
    print("\n[1/4] 输入页面标题关键字（支持模糊匹配）：")
    title = input("  > ").strip()
    if not title:
        print("  未输入标题，退出。")
        return

    # ---- 步骤 2: 选择站点 ----
    print("\n[2/4] 选择站点范围：")
    for key, (name, _) in SITE_PRESETS.items():
        print(f"  [{key}] {name}")
    site_choice = input("  > ").strip()
    site_url = None
    if site_choice in SITE_PRESETS:
        _, site_url = SITE_PRESETS[site_choice]
    else:
        _, site_url = SITE_PRESETS["8"]

    if site_url:
        print(f"  已选择: {site_url}")
    else:
        print(f"  已选择: 所有站点")

    # ---- 步骤 3: 选择排序 ----
    print("\n[3/4] 选择排序方式：")
    for key, (name, _, _) in SORT_OPTIONS.items():
        print(f"  [{key}] {name}")
    sort_choice = input("  > ").strip()
    if sort_choice in SORT_OPTIONS:
        _, sort_key, sort_order = SORT_OPTIONS[sort_choice]
    else:
        _, sort_key, sort_order = SORT_OPTIONS["1"]
    print(f"  已选择: {sort_key} {sort_order}")

    # ---- 步骤 4: 选择字段 ----
    print("\n[4/4] 选择返回字段：")
    print("  预设方案：")
    for key, preset in PRESETS.items():
        desc = ", ".join(preset["fields"]) if preset["fields"] else "手动勾选"
        print(f"  [{key}] {preset['name']}: {desc}")
    print(f"  [5] 手动逐个选择字段")

    field_choice = input("  > ").strip()

    if field_choice == "5":
        fields = select_fields_interactively()
    elif field_choice in PRESETS:
        preset = PRESETS[field_choice]
        if preset["fields"] is None:
            fields = select_fields_interactively()
        else:
            fields = preset["fields"] + ["url"]
            # 去重 url
            fields = list(dict.fromkeys(fields))
    else:
        fields = PRESETS["1"]["fields"] + ["url"]

    print(f"\n  选中字段: {', '.join(fields)}")

    # ---- 执行查询 ----
    page_size = 10
    cursors: list[str] = []  # 分页历史（用于后退）

    while True:
        print(f"\n{'-' * 60}")
        print("  正在查询...")

        after_cursor = cursors[-1] if cursors else None
        query_str = build_query(
            title_filter=title,
            site_url=site_url,
            fields=fields,
            sort_key=sort_key,
            sort_order=sort_order,
            first=page_size,
            after=after_cursor,
        )

        try:
            result = gql_request(query_str)
        except RuntimeError as e:
            print(f"\n  [X] 查询失败: {e}")
            break

        if "errors" in result:
            print("\n  [X] GraphQL 错误：")
            for err in result["errors"]:
                print(f"    - {err.get('message', str(err))}")
            break

        page_info = display_results(result, fields, page_size)

        if page_info is None:
            break

        # ---- 导航 ----
        has_next = page_info.get("hasNextPage", False)
        has_prev = len(cursors) > 0

        if has_next or has_prev:
            options = []
            if has_next:
                options.append("[N] 下一页")
            if has_prev:
                options.append("[P] 上一页")
            options.append("[Q] 退出")

            print(f"\n  {' | '.join(options)}")
            nav = input("  > ").strip().upper()

            if nav == "N" and has_next:
                cursors.append(page_info.get("endCursor", ""))
            elif nav == "P" and has_prev:
                cursors.pop()
            elif nav == "Q":
                break
            else:
                break
        else:
            if len(cursors) > 0:
                print("\n  [P] 上一页 | [Q] 退出")
                nav = input("  > ").strip().upper()
                if nav == "P":
                    cursors.pop()
                    continue
            break

    print(f"\n  查询结束。\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  已取消。\n")
    except EOFError:
        print("\n")
