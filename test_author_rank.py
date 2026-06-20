"""Test author ranking queries - deeper exploration."""
import asyncio, sys, json
sys.path.insert(0, '.')
from server import _gql_request

async def introspect_user_stats():
    print("=== UserStatistics fields ===")
    query = """query {
      __type(name: "UserStatistics") {
        name
        fields { name type { name kind ofType { name kind } } }
      }
    }"""
    result = await _gql_request(query)
    print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])

async def test_full_rank():
    print("\n=== usersByRank_v1(rank: 1) full query ===")
    query = """query {
      usersByRank_v1(rank: 1, siteUrl: "http://scp-wiki-cn.wikidot.com/") {
        id
        displayName
        statistics {
          __typename
        }
        userPage {
          url
        }
      }
    }"""
    result = await _gql_request(query)
    print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])

async def test_statistics():
    print("\n=== UserStatistics all fields ===")
    # First introspect
    query = """query {
      usersByRank_v1(rank: 1) {
        displayName
        statistics {
          pageCount
        }
      }
    }"""
    result = await _gql_request(query)
    print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])

    print("\n=== Try other stat field names ===")
    for field in ["pageCount", "editCount", "ratingSum", "voteSum", "averageRating",
                  "rank", "score", "totalRating", "pageCount_v1"]:
        query = f"""query {{
          usersByRank_v1(rank: 1) {{
            displayName
            statistics {{
              {field}
            }}
          }}
        }}"""
        result = await _gql_request(query)
        if "errors" in result:
            print(f"  {field}: ERROR - {result['errors'][0]['message'][:100]}")
        else:
            data = result.get("data", {}).get("usersByRank_v1", [])
            if data:
                stats = data[0].get("statistics", {})
                print(f"  {field}: {stats.get(field, 'null')}")

async def test_attributed_pages():
    print("\n=== attributedPages ===")
    query = """query {
      __type(name: "AttributedPageConnection") {
        name
        fields { name type { name kind ofType { name kind } } }
      }
    }"""
    result = await _gql_request(query)
    print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])

async def main():
    await introspect_user_stats()
    await test_full_rank()
    await test_statistics()
    await test_attributed_pages()

if __name__ == "__main__":
    asyncio.run(main())
