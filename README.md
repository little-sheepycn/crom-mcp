# crom-mcp

MCP 服务器，用于查询 [Crom API v2](https://apiv2.crom.avn.sh/graphql) —— 一个汇总 SCP 基金会各 Wikidot 站点结构化数据的 GraphQL API。

## 快速开始

```bash
# 安装依赖
uv venv
uv pip install -r requirements.txt
```

### MCP 客户端配置

```json
{
  "mcpServers": {
    "crom-mcp": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/crom-plugin", "server.py"]
    }
  }
}
```

无需 API Key，Crom API 的只读查询是公开的。

## 工具列表

### 页面查询

| 工具 | 说明 |
|------|------|
| `crom_search` | 综合搜索：标题关键词 + 作者 + 标签 + 站点，AND 关系组合过滤 |
| `crom_search_pages` | 按标题关键词模糊搜索（前缀匹配），支持排序和分页 |
| `crom_get_page` | 按完整 Wikidot URL 获取单个页面详情 |
| `crom_get_child_pages` | 获取指定页面的所有子页面（系列/故事集导航） |
| `crom_get_page_source` | 获取页面的 Wikidot 源码和/或纯文本内容 |
| `crom_search_by_tag` | 按标签搜索（如 `scp`、`keter`、`safe`、`joke`） |
| `crom_search_by_author` | 按作者署名搜索，支持角色过滤（作者/译者/重写） |

### 用户与作者

| 工具 | 说明 |
|------|------|
| `crom_get_user` | 按 displayName 查询 Wikidot 用户 |
| `crom_get_author_stats` | 查询作者统计：排名、总评分、均分、各类型作品数 |
| `crom_get_top_authors` | 按排名区间查询作者排行榜 |

### 论坛

| 工具 | 说明 |
|------|------|
| `crom_get_forum_thread` | 按帖子 ID 获取论坛主题详情 |
| `crom_get_forum_post` | 按回复 ID 获取论坛回复内容 |

### 工具

| 工具 | 说明 |
|------|------|
| `crom_list_sites` | 列出 Crom API 支持的所有站点 |

## 支持的站点

| 标识 | 站点 | URL |
|------|------|-----|
| `scp-en` | SCP-EN | `http://scp-wiki.wikidot.com/` |
| `scp-cn` | SCP-CN | `http://scp-wiki-cn.wikidot.com/` |
| `scp-int` | SCP-INT | `http://scp-int.wikidot.com/` |
| `scp-ru` | SCP-RU | `http://scp-ru.wikidot.com/` |
| `scp-fr` | SCP-FR | `http://fondationscp.wikidot.com/` |
| `wanderers` | 流浪者图书馆 | `http://wanderers-library.wikidot.com/` |
| `backrooms` | 后室 | `http://backrooms-wiki.wikidot.com/` |

## 技术栈

- Python 3.12+，使用 `uv` 管理
- [FastMCP](https://github.com/jlowin/fastmcp) + stdio transport
- `httpx` 异步 HTTP 请求
- 无需认证、零配置

## 许可证

[AGPLv3](LICENSE)
