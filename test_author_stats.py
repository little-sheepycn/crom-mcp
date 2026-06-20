"""Explore ways to get author stats by name."""
import asyncio, sys, json
sys.path.insert(0, '.')
from server import _gql_request

async def test_search_users():
    print("=== searchUsers_v1('W Asriel') ===")
    query = """query {
      searchUsers_v1(query: "W Asriel") {
        ... on UserWikidotNameReference {
          displayName
          statistics {
            rank
            totalRating
            meanRating
            pageCount
            pageCountScp
            pageCountTale
            pageCountGoiFormat
            pageCountArtwork
          }
        }
      }
    }"""
    result = await _gql_request(query)
    print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])

async def test_wikidot_user():
    print("\n=== wikidotUser('W Asriel') ===")
    query = """query {
      wikidotUser(displayName: "W Asriel") {
        displayName
        wikidotId
      }
    }"""
    result = await _gql_request(query)
    print(json.dumps(result, indent=2, ensure_ascii=False)[:800])

async def test_user_with_id():
    print("\n=== user(id) with statistics ===")
    query = """query {
      user(id: "3317001") {
        ... on UserWikidotNameReference {
          displayName
          statistics {
            rank
            totalRating
            meanRating
            pageCount
          }
        }
      }
    }"""
    result = await _gql_request(query)
    print(json.dumps(result, indent=2, ensure_ascii=False)[:1200])

async def introspect_wikidot_user():
    print("\n=== WikidotUser fields ===")
    query = """query {
      __type(name: "WikidotUser") {
        fields { name }
      }
    }"""
    result = await _gql_request(query)
    print(json.dumps(result, indent=2, ensure_ascii=False)[:1200])

    print("\n=== User interface implementations ===")
    query = """query {
      __type(name: "User") {
        possibleTypes { name }
      }
    }"""
    result = await _gql_request(query)
    print(json.dumps(result, indent=2, ensure_ascii=False)[:1200])

async def main():
    await test_wikidot_user()
    await test_search_users()
    await test_user_with_id()
    await introspect_wikidot_user()

if __name__ == "__main__":
    asyncio.run(main())
