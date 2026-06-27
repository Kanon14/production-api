"""
test_monitoring.py

Simple test cases and usage samples for monitoring.py.

This file tests:
1. JSON logger creation
2. RequestTimer latency measurement
3. MetricsCollector normal request tracking
4. MetricsCollector error tracking
5. Cache hit / miss tracking
6. Final metrics summary
"""

import time
import json

from app.monitoring import get_logger, MetricsCollector, RequestTimer


def test_logger():
    """
    Test that the logger can output structured JSON logs.
    """

    logger = get_logger("test-api")

    logger.info(
        "Logger test completed",
        extra={
            "extra_data": {
                "test_name": "test_logger",
                "status": "passed",
            }
        },
    )


def test_request_timer():
    """
    Test that RequestTimer measures elapsed time correctly.
    """

    with RequestTimer() as timer:
        time.sleep(0.1)

    assert timer.elapsed_ms > 0
    assert timer.elapsed_ms >= 90

    print("test_request_timer passed")
    print(f"Measured latency: {timer.elapsed_ms:.2f} ms")


def test_metrics_success_request():
    """
    Test recording a successful request.
    """

    metrics = MetricsCollector()

    metrics.record_request(
        latency_ms=150.5,
        input_tokens=100,
        output_tokens=50,
        error=False,
        cache_hit=False,
    )

    summary = metrics.summary

    assert summary["total_requests"] == 1
    assert summary["total_errors"] == 0
    assert summary["error_rate"] == "0.00%"
    assert summary["avg_latency_ms"] == 150.5
    assert summary["cache_hits"] == 0
    assert summary["cache_misses"] == 1
    assert summary["cache_hit_rate"] == "0.00%"
    assert summary["total_input_tokens"] == 100
    assert summary["total_output_tokens"] == 50
    assert summary["total_tokens"] == 150

    print("test_metrics_success_request passed")


def test_metrics_error_request():
    """
    Test recording a failed request.
    """

    metrics = MetricsCollector()

    metrics.record_request(
        latency_ms=80.0,
        input_tokens=30,
        output_tokens=0,
        error=True,
        cache_hit=None,
    )

    summary = metrics.summary

    assert summary["total_requests"] == 1
    assert summary["total_errors"] == 1
    assert summary["error_rate"] == "100.00%"
    assert summary["avg_latency_ms"] == 80.0
    assert summary["cache_hits"] == 0
    assert summary["cache_misses"] == 0
    assert summary["cache_hit_rate"] == "0.00%"
    assert summary["total_input_tokens"] == 30
    assert summary["total_output_tokens"] == 0
    assert summary["total_tokens"] == 30

    print("test_metrics_error_request passed")


def test_metrics_multiple_requests():
    """
    Test metrics aggregation across multiple requests.
    """

    metrics = MetricsCollector()

    # Request 1: cache miss
    metrics.record_request(
        latency_ms=100,
        input_tokens=50,
        output_tokens=25,
        error=False,
        cache_hit=False,
    )

    # Request 2: cache hit
    metrics.record_request(
        latency_ms=20,
        input_tokens=50,
        output_tokens=25,
        error=False,
        cache_hit=True,
    )

    # Request 3: error, cache not checked
    metrics.record_request(
        latency_ms=200,
        input_tokens=40,
        output_tokens=0,
        error=True,
        cache_hit=None,
    )

    summary = metrics.summary

    assert summary["total_requests"] == 3
    assert summary["total_errors"] == 1
    assert summary["error_rate"] == "33.33%"
    assert summary["avg_latency_ms"] == 106.67
    assert summary["cache_hits"] == 1
    assert summary["cache_misses"] == 1
    assert summary["cache_hit_rate"] == "50.00%"
    assert summary["total_input_tokens"] == 140
    assert summary["total_output_tokens"] == 50
    assert summary["total_tokens"] == 190

    print("test_metrics_multiple_requests passed")


def sample_rag_request(metrics: MetricsCollector, query: str, use_cache: bool = False):
    """
    Simulate one RAG API request.

    This is only a sample.
    Replace the fake logic with your real RAG chain later.
    """

    logger = get_logger("rag-api")

    try:
        with RequestTimer() as timer:
            # Simulate cache behavior
            if use_cache:
                time.sleep(0.02)
                response = "Cached RAG response"
                input_tokens = 0
                output_tokens = 0
                cache_hit = True
            else:
                # Simulate retrieval + LLM generation
                time.sleep(0.15)
                response = f"Generated answer for query: {query}"
                input_tokens = 120
                output_tokens = 60
                cache_hit = False

        metrics.record_request(
            latency_ms=timer.elapsed_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error=False,
            cache_hit=cache_hit,
        )

        logger.info(
            "RAG request completed",
            extra={
                "extra_data": {
                    "query": query,
                    "latency_ms": round(timer.elapsed_ms, 2),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_hit": cache_hit,
                }
            },
        )

        return response

    except Exception as e:
        metrics.record_request(
            latency_ms=0.0,
            error=True,
            cache_hit=None,
        )

        logger.error(
            "RAG request failed",
            extra={
                "extra_data": {
                    "query": query,
                    "error": str(e),
                }
            },
        )

        return None


def sample_failed_request(metrics: MetricsCollector):
    """
    Simulate a failed API request.
    """

    logger = get_logger("rag-api")

    try:
        with RequestTimer() as timer:
            time.sleep(0.05)
            raise RuntimeError("Vector database connection failed")

    except Exception as e:
        metrics.record_request(
            latency_ms=timer.elapsed_ms,
            input_tokens=20,
            output_tokens=0,
            error=True,
            cache_hit=None,
        )

        logger.error(
            "Request failed",
            extra={
                "extra_data": {
                    "latency_ms": round(timer.elapsed_ms, 2),
                    "error": str(e),
                }
            },
        )


def run_all_tests():
    """
    Run all test cases.
    """

    print("\nRunning monitoring tests...\n")

    test_logger()
    test_request_timer()
    test_metrics_success_request()
    test_metrics_error_request()
    test_metrics_multiple_requests()

    print("\nAll tests passed.\n")


def run_sample_app():
    """
    Run sample monitoring flow.
    """

    print("\nRunning sample RAG monitoring flow...\n")

    metrics = MetricsCollector()

    response_1 = sample_rag_request(
        metrics=metrics,
        query="What is RAG?",
        use_cache=False,
    )

    response_2 = sample_rag_request(
        metrics=metrics,
        query="What is RAG?",
        use_cache=True,
    )

    sample_failed_request(metrics)

    print("\nSample responses:")
    print(response_1)
    print(response_2)

    print("\nMetrics summary:")
    print(json.dumps(metrics.summary, indent=2))


def main():
    """
    Main entry point.

    This runs:
    1. Unit-style test cases
    2. A simple sample RAG monitoring simulation
    """

    run_all_tests()
    run_sample_app()


if __name__ == "__main__":
    main()