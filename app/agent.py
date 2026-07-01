from typing import Optional
from typing_extensions import TypedDict, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from langsmith import traceable

from app.config import get_settings


class AgentState(TypedDict):
    """
    State object used by the LangGraph agent.

    Fields:
        messages:
            Conversation messages.
            add_messages reducer allows new messages to be appended automatically.

        error:
            Stores the latest error message if a model call fails.

        retry_count:
            Tracks how many failed attempts happened.

        model_used:
            Stores which model path was used:
            - "primary"
            - "fallback"
            - "error_handler"
    """

    messages: Annotated[list[BaseMessage], add_messages]
    error: Optional[str]
    retry_count: int
    model_used: str


class ProductionAgent:
    """
    Production LangGraph agent.

    Features:
    - Primary LLM call
    - Fallback LLM call if the primary model fails
    - Graceful error response if both fail
    - LangSmith tracing
    """

    def __init__(self) -> None:
        settings = get_settings()

        # Primary model used for normal requests.
        self.primary_llm = ChatOpenAI(
            model=settings.primary_model,
            api_key=settings.openai_api_key,
            temperature=0,
            timeout=30,
            max_retries=0,
        )

        # Fallback model used when the primary model fails.
        self.fallback_llm = ChatOpenAI(
            model=settings.fallback_model,
            api_key=settings.openai_api_key,
            temperature=0,
            timeout=30,
            max_retries=0,
        )

        # Maximum retry count from app settings.
        # In this graph, one failure from primary can route to fallback.
        self.max_retries = settings.max_retries

        # Compile the LangGraph state machine.
        self.graph = self._build_graph()

    def save_graph_image(self, output_path: str = "langgraph_agent.png") -> str:
        """
        Save the LangGraph workflow as a PNG image.

        This function is optional and mainly useful for:
        - Documentation
        - README screenshots
        - Debugging graph structure
        - Explaining the agent workflow

        Args:
            output_path:
                File path where the graph image should be saved.

        Returns:
            The output path of the saved graph image.

        Example:
            agent = ProductionAgent()
            agent.save_graph_image("docs/langgraph_agent.png")
        """
        try:
            graph_png = self.graph.get_graph().draw_mermaid_png()

            with open(output_path, "wb") as file:
                file.write(graph_png)

            return output_path

        except Exception as e:
            raise RuntimeError(f"Failed to save LangGraph image: {e}") from e

    def _build_graph(self):
        """
        Build and compile the LangGraph state machine.

        Flow:
            START
              -> process primary model
              -> if success: END
              -> if failure and retry allowed: fallback model
              -> if fallback success: END
              -> if fallback failure: error handler
              -> END
        """

        def process_message(state: AgentState) -> dict:
            """
            Try to process the message with the primary model.

            Input:
                state["messages"]

            Output:
                dict containing:
                - messages if successful
                - error if failed
                - retry_count increment if failed
                - model_used
            """
            try:
                response = self.primary_llm.invoke(state["messages"])

                return {
                    "messages": [response],
                    "error": None,
                    "model_used": "primary",
                }

            except Exception as e:
                return {
                    "error": str(e),
                    "retry_count": state["retry_count"] + 1,
                    "model_used": "",
                }

        def try_fallback(state: AgentState) -> dict:
            """
            Try to process the message with the fallback model.

            This runs only if the primary model fails.
            """
            try:
                response = self.fallback_llm.invoke(state["messages"])

                return {
                    "messages": [response],
                    "error": None,
                    "model_used": "fallback",
                }

            except Exception as e:
                return {
                    "error": str(e),
                    "model_used": "",
                }

        def handle_error(state: AgentState) -> dict:
            """
            Return a user-friendly error response.

            This prevents raw system/model errors from being exposed to the user.
            """
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I'm sorry, I'm having trouble processing your request "
                            "right now. Please try again in a moment."
                        )
                    )
                ],
                "model_used": "error_handler",
            }

        def route_after_process(state: AgentState) -> str:
            """
            Decide route after the primary model attempt.

            Returns:
                "done"     -> primary model succeeded
                "fallback" -> primary failed, try fallback
                "error"    -> primary failed and retry limit reached
            """
            if state.get("error") is None:
                return "done"
            elif state["retry_count"] <= self.max_retries:
                return "fallback"
            else:
                return "error"

        def route_after_fallback(state: AgentState) -> str:
            """
            Decide route after fallback model attempt.

            Returns:
                "done"  -> fallback succeeded
                "error" -> fallback failed
            """
            if state.get("error") is None:
                return "done"
            else:
                return "error"

        # Build LangGraph.
        graph = StateGraph(AgentState)

        graph.add_node("process", process_message)
        graph.add_node("fallback", try_fallback)
        graph.add_node("error", handle_error)

        graph.add_edge(START, "process")

        graph.add_conditional_edges(
            "process",
            route_after_process,
            {
                "done": END,
                "fallback": "fallback",
                "error": "error",
            },
        )

        graph.add_conditional_edges(
            "fallback",
            route_after_fallback,
            {
                "done": END,
                "error": "error",
            },
        )

        graph.add_edge("error", END)

        return graph.compile()

    @traceable(name="production_agent_invoke")
    def invoke(self, message: str) -> dict:
        """
        Invoke the production agent with a user message.

        Args:
            message:
                User query string.

        Returns:
            dict:
                {
                    "response": str,
                    "model_used": str,
                    "error": str | None
                }
        """

        initial_state: AgentState = {
            "messages": [HumanMessage(content=message)],
            "error": None,
            "retry_count": 0,
            "model_used": "",
        }

        result = self.graph.invoke(initial_state)

        return {
            "response": result["messages"][-1].content,
            "model_used": result.get("model_used", "unknown"),
            "error": result.get("error"),
        }