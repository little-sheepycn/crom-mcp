# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Crom Plugin is a Python toolset for querying the [Crom API v2](https://apiv2.crom.avn.sh/graphql), a GraphQL API that serves structured data from SCP Foundation wikidot sites (SCP-CN, SCP-EN, Wanderer's Library, Backrooms, etc.).

## Tech Stack

- Python 3.12, managed with `uv`
- No runtime dependencies (uses `urllib.request` from stdlib)
- USTC PyPI mirror configured in `pyproject.toml`

## Commands

```bash
# Run the interactive query tool
python reference/crom_query.py

# Run the placeholder entry point
python main.py
```

## Architecture

The core module is `reference/crom_query.py`, a zero-dependency CLI that:

1. **Interactive 4-step wizard**: title keyword → site filter → sort order → field selection
2. **GraphQL query builder** (`build_query`): Constructs `pages` queries with `_or` logic to match both `onWikidotPage.title` and `alternateTitles.title` via `startsWithLower`. When a site is specified, wraps the `_or` in an `_and` with a `url` prefix filter.
3. **Field fragment builder** (`build_fields_selection`): Maps user-selected fields to GraphQL fragments. Common interface fields (`ResolvedPage`) go directly under `node`. Wikidot-specific fields (`WikidotPage`) are merged into a single `... on WikidotPage` inline fragment — critical: multiple separate fragments cause server errors.
4. **SSL fallback**: Uses `ssl._create_unverified_context()` on Windows when CA certs are missing.
5. **GBK encoding workaround**: Replaces Unicode box-drawing/special chars with ASCII equivalents for Windows terminals.

**Preset field groups** (in `PRESETS`):
- `1`: Basic info — title, rating, voteCount, category, createdAt
- `2`: Basic + author — preset 1 + createdBy, attributions
- `3`: Full info — all 20+ fields including source, textContent, thread, children, etc.

**Site presets** cover SCP-CN, SCP-EN, SCP-INT, SCP-RU, SCP-FR, Wanderer's Library, Backrooms.

## Reference Files

| File | Purpose |
|------|---------|
| `reference/crom-api-docs.md` | Full API docs: 19 queries, 15 mutations, field descriptions, rate limits |
| `reference/pages-query.graphql` | Example `pages` queries (filter, sort, pagination) |
| `reference/pages-query-by-author.graphql` | Examples for filtering by `attributions.type` + `user.displayName` |
| `reference/pages-query-by-title.graphql` | Examples for `title` filtering with `eqLower`/`startsWithLower` |

## Key API Patterns

- **Relay pagination**: `edges { node { ... } cursor }` + `pageInfo { hasNextPage endCursor }`; use `after` for next page
- **Filter operators**: `eq`, `neq`, `lt`, `lte`, `gt`, `gte` on scalars; `eqLower`/`startsWithLower` for case-insensitive string matching
- **Boolean logic**: `_and`, `_or`, `_not` at each filter level
- **Wikidot URLs**: Always `http://` (not `https://`) regardless of the site's actual protocol
- **Sort keys**: `WIKIDOT_RATING`, `WIKIDOT_CREATED_AT`, `WIKIDOT_TITLE`, `LATEST_ATTRIBUTION_DATE`

## Known API Issues

- The `alternateTitles` filter on `PageQueryFilter` can cause `INTERNAL_SERVER_ERROR` when used as the only match branch — the `_or` pattern (matching both `title` + `alternateTitles`) works as long as the `title` branch can match
- Multiple `... on WikidotPage` inline fragments on the same node cause validation errors; always merge into one fragment
