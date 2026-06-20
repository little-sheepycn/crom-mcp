# Crom API v2 文档

**GraphQL Endpoint:** `https://apiv2.crom.avn.sh/graphql`
**Playground:** 浏览器打开上述 URL 即可使用 Altair GraphQL IDE 交互式查询。

---

## Query 类型（19 个）

### 账户 & 应用

| Query | 参数 | 返回类型 | 说明 |
|-------|------|----------|------|
| `account` | `id: ID!` | `Account` | 通过 ID 获取账户。目前仅返回自己的账户。 |
| `application` | `id: ID!` | `Application` | 通过 ID 获取应用。 |
| `viewer` | 无 | `Viewer!` | 获取当前 access token 的元数据。 |

### 页面

| Query | 参数 | 返回类型 | 说明 | 速率消耗 |
|-------|------|----------|------|----------|
| `page` | `url: URL!` | `ResolvedPage` | 通过 URL 获取页面。Wikidot URL 始终用 http://。 | 1 pts |
| `pages` | `filter`, `sort`, `before`, `after`, `first`, `last` | `PageConnection!` | 自定义筛选查询页面列表，遵循 Relay 分页规范。默认 page size=100。 | 1 pts × page size |
| `aggregatePages` | `filter` | `PageAggregation!` | 获取页面聚合统计数据。 | 2 pts |
| `matchingPages` | `url: URL!` | `[ResolvedPage!]!` | 获取相关站点上匹配路径的页面列表（interwiki 用）。 | 20 pts |
| `wikidotPage` | `url`, `wikidotId` | `WikidotPage` | 通过 URL 或 Wikidot ID 获取 Wikidot 页面。 | 1 pts |
| `ruFoundationPage` | `url` | `RuFoundationPage` | 通过 URL 获取 RU Foundation 页面。 | 1 pts |

### 随机 & 搜索（旧版兼容，不建议使用）

| Query | 参数 | 返回类型 | 说明 | 速率消耗 |
|-------|------|----------|------|----------|
| `randomPage_v1` | `filter` | `ResolvedPage` | 获取随机匹配页面。返回 null 若无匹配。 | 5 pts |
| `searchPages_v1` | `query: String!`, `siteUrl: URL!` | `[ResolvedPage!]!` | 搜索页面。 | 1 pts |

### 用户

| Query | 参数 | 返回类型 | 说明 | 速率消耗 |
|-------|------|----------|------|----------|
| `user` | `id: ID!` | `User` | 通过 ID 获取用户。 | 1 pts |
| `wikidotUser` | `displayName`, `wikidotId` | `WikidotUser` | 通过 displayName 或 wikidotId 获取 Wikidot 用户。 | 1 pts |
| `searchUsers_v1` | `query: String!`, `siteUrl` | `[User!]!` | 搜索用户（旧版兼容）。 | 1 pts |
| `usersByRank_v1` | `rank: Int!`, `siteUrl` | `[User!]!` | 按 rank 获取用户（旧版兼容）。 | 2 pts |

### 阅读列表

| Query | 参数 | 返回类型 | 说明 | 速率消耗 |
|-------|------|----------|------|----------|
| `readingList` | `id`, `slug` | `ReadingList` | 通过 ID 或 slug 获取阅读列表。 | 1 pts |

### 论坛

| Query | 参数 | 返回类型 | 说明 | 速率消耗 |
|-------|------|----------|------|----------|
| `wikidotForumThread` | `threadId: ID!` | `WikidotForumThread` | 通过 thread ID 获取论坛帖子。 | 1 pts |
| `wikidotForumPost` | `postId: ID!` | `WikidotForumPost` | 通过 post ID 获取论坛回帖。 | 1 pts |

### 站点元数据

| Query | 参数 | 返回类型 | 说明 |
|-------|------|----------|------|
| `sites` | 无 | `[Site!]!` | 返回 Crom 支持的站点列表及元数据。 |

---

## Mutation 类型（15 个）

### 账户管理（需 `MANAGE_ACCOUNT` scope）

| Mutation | 参数 | 说明 |
|----------|------|------|
| `deleteAccountWikidotIntegration` | 无 | 移除当前账户的 Wikidot 集成。 |
| `deleteAccountDiscordIntegration` | 无 | 移除当前账户的 Discord 集成。 |
| `deleteAccountPatreonIntegration` | 无 | 移除当前账户的 Patreon 集成。 |
| `deleteAccount` | 无 | 删除整个账户。 |

### 应用管理（需 `MANAGE_ACCOUNT` scope）

| Mutation | 参数 | 说明 |
|----------|------|------|
| `createApplication` | `input: CreateApplicationInput!` | 创建新应用。 |
| `updateApplication` | `input: UpdateApplicationInput!` | 更新已有应用。 |
| `deleteApplication` | `input: DeleteApplicationInput!` | 删除应用。 |

### 爬虫提示

| Mutation | 参数 | 说明 |
|----------|------|------|
| `submitCrawlerHint` | `input: SubmitCrawlerHintInput!` | 请求排队更新网页爬虫数据。重复请求会被限流，错误提示可能导致后续被忽略。 |

### 日记条目（需 `MANAGE_DIARY_ENTRIES` scope，各 3 pts）

| Mutation | 参数 | 说明 |
|----------|------|------|
| `createDiaryEntry` | `input: CreateDiaryEntryInput!` | 创建日记条目。 |
| `updateDiaryEntry` | `input: UpdateDiaryEntryInput!` | 更新日记条目。 |
| `deleteDiaryEntry` | `input: DeleteDiaryEntryInput!` | 删除日记条目。 |

### 阅读列表（需 `MANAGE_READING_LISTS` scope）

| Mutation | 参数 | 说明 | 速率消耗 |
|----------|------|------|----------|
| `createReadingList` | `input: CreateReadingListInput!` | 创建新的阅读列表。 | 100 pts |
| `updateReadingList` | `input: UpdateReadingListInput!` | 更新已有阅读列表。 | 10 pts |
| `deleteReadingList` | `input: DeleteReadingListInput!` | 删除已有阅读列表。 | 10 pts |
| `cloneReadingList` | `input: CloneReadingListInput!` | 克隆已有阅读列表（新列表始终为 PRIVATE）。 | 100 pts |

---

## 关键说明

- **分页**：遵循 [Relay Connection](https://relay.dev/graphql/connections.htm) 规范（`before`/`after`/`first`/`last`）。
- **速率限制**：以 points 为单位，不同操作消耗 1~100 pts 不等。
- **筛选逻辑**：`pages` query 的 `filter` 参数支持 `eq`、`neq`、`lt`、`gt` 等操作符。同一字段多个操作符用 AND 组合；非基本类型字段用 `_and`/`_or`/`_not` 进行布尔组合。
- **旧版兼容**：带 `_v1` 后缀的 query 仅用于内部兼容，不建议新开发使用。
- **Wikidot URL**：始终以 `http://` 格式存储和查询，无论站点是否支持 HTTPS。
