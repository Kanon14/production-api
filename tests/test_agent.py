from app.agent import ProductionAgent


def main() -> None:
    """
    Simple test script for ProductionAgent.

    Run:
        python test_agent.py

    Make sure your .env/config contains:
        - OPENAI_API_KEY
        - PRIMARY_MODEL
        - FALLBACK_MODEL
        - MAX_RETRIES
    """

    agent = ProductionAgent()

    test_queries = [
        "What is RAG? Explain in 2 sentences.",
        "Give me 3 benefits of using connection pooling in a production API.",
        "Write a simple Python function that adds two numbers.",
    ]

    for index, query in enumerate(test_queries, start=1):
        print("=" * 80)
        print(f"Test Query {index}")
        print("=" * 80)

        print("User Query:")
        print(query)

        result = agent.invoke(query)

        print("\nAgent Response:")
        print(result["response"])

        print("\nMetadata:")
        print(f"Model used: {result['model_used']}")
        print(f"Error: {result['error']}")

    print("=" * 80)
    print("ProductionAgent test completed.")


if __name__ == "__main__":
    main()