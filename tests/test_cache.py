import time
from app.cache import ResponseCache

def main():
    # Use short TTL for testing expiry quickly
    cache = ResponseCache(ttl_seconds=3)

    query_1 = "What is Python?"
    response_1 = "Python is a high-level programming language."

    query_2 = "What is RAG?"
    response_2 = "RAG stands for Retrieval-Augmented Generation."

    print("=" * 80)
    print("TEST 1: Initial cache miss")
    print("=" * 80)

    result = cache.get(query_1)
    print(f"Query: {query_1}")
    print(f"Cached result: {result}")
    print(f"Stats: {cache.stats}")

    print("\n" + "=" * 80)
    print("TEST 2: Set cache value")
    print("=" * 80)

    cache.set(query_1, response_1)
    print(f"Cached response for query: {query_1}")
    print(f"Stats: {cache.stats}")

    print("\n" + "=" * 80)
    print("TEST 3: Cache hit")
    print("=" * 80)

    result = cache.get(query_1)
    print(f"Query: {query_1}")
    print(f"Cached result: {result}")
    print(f"Stats: {cache.stats}")

    print("\n" + "=" * 80)
    print("TEST 4: Normalized query should hit same cache")
    print("=" * 80)

    # Same query with different case and extra spaces
    normalized_query = "   what is python?   "
    result = cache.get(normalized_query)

    print(f"Original query: {query_1}")
    print(f"Normalized query test: {normalized_query}")
    print(f"Cached result: {result}")
    print(f"Stats: {cache.stats}")

    print("\n" + "=" * 80)
    print("TEST 5: Another query miss, then set")
    print("=" * 80)

    result = cache.get(query_2)
    print(f"Query: {query_2}")
    print(f"Cached result before set: {result}")

    cache.set(query_2, response_2)
    result = cache.get(query_2)

    print(f"Cached result after set: {result}")
    print(f"Stats: {cache.stats}")

    print("\n" + "=" * 80)
    print("TEST 6: TTL expiry")
    print("=" * 80)

    print("Waiting 4 seconds for cache to expire...")
    time.sleep(4)

    result = cache.get(query_1)
    print(f"Query after TTL expiry: {query_1}")
    print(f"Cached result: {result}")
    print(f"Stats: {cache.stats}")

    print("\n" + "=" * 80)
    print("TEST 7: Final cache stats")
    print("=" * 80)

    print(cache.stats)


if __name__ == "__main__":
    main()