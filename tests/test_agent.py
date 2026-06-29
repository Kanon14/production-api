from app.agent import ProductionAgent


def main() -> None:
    agent = ProductionAgent()

    # Optional: save LangGraph workflow image
    image_path = agent.save_graph_image("langgraph_agent.png")
    print(f"LangGraph image saved to: {image_path}")

    test_queries = [
        "What is RAG? Explain in 2 sentences.",
        "Give me 3 benefits of using connection pooling in a production API.",
        "Write a simple Python function that adds two numbers.",
    ]

    for index, query in enumerate(test_queries, start=1):
        print("=" * 80)
        print(f"Test Query {index}")
        print("=" * 80)

        result = agent.invoke(query)

        print(f"Query: {query}")
        print(f"Response: {result['response']}")
        print(f"Model used: {result['model_used']}")
        print(f"Error: {result['error']}")


if __name__ == "__main__":
    main()