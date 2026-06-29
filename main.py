import time
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from langsmith import traceable
from dotenv import load_dotenv

from app.config import get_settings
from app.models import (
    ChatRequest, ChatResponse, 
    HealthResponse, MetricsResponse, ErrorResponse
)
from app.security import SecurityPipeline
from app.cache import ResponseCache
from app.monitoring import get_logger, MetricsCollector, RequestTimer
from app.agent import ProductionAgent

load_dotenv()

security: SecurityPipeline = None
cache: ResponseCache = None
metrics: MetricsCollector = None
agent: ProductionAgent = None
logger = get_logger()

# === Lifespan (startup/shutdown) ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize all components on startup, clean up on shutdown.
    This is the modern FastAPI pattern (replaces @app.on_event).
    """
    global security, cache, metrics, agent
    
    settings = get_settings()
    
    logger.info("Starting production API", 
                extra={
                    "extra_data": {
                        "environment": settings.app_env,
                        "primary_model": settings.primary_model,
                        "tracing_enabled": settings.langchain_tracing_v2,
                        }
                    }
                )
    
    # Initialize components
    security = SecurityPipeline()
    cache = ResponseCache(ttl_seconds=settings.cache_ttl_seconds)
    metrics = MetricsCollector()
    agent = ProductionAgent()
    
    logger.info("All components initialized. Ready to serve requests.")
    
    yield # App is running
    
    # Shutdown
    logger.info("Shutting down...", 
                extra={
                    "extra_data": metrics.summary
                }
                )
    
# === Rate Limiter Setup ===
limiter = Limiter(key_func=get_remote_address)

# === FastAPI App ===
app = FastAPI(
    title="Production LangGraph API",
    description="A production-ready chat API with security, caching, and observability.",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter


# === Exception Handlers ===
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Handle rate limit errors globally.
    This runs whenever a route exceeds its allowed request limit.
    """
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": "Too many requests. Please slow down."
        },
    )
    
# ==========================================================
# ENDPOINTS
# ==========================================================

@app.post("/chat", response_model=ChatResponse)
@limiter.limit(get_settings().rate_limit)
@traceable(name="chat_endpoint")
async def chat(request: Request, body: ChatRequest):
    """
    Main chat endpoint.
    
    Flow:
    1. Security check (injection + PII masking)
    2. Cache lookup
    3. langGraph agent invoke (if cache miss)
    4. Output validation
    5. Cache store
    6. Return response
    """
    with RequestTimer() as timer:
        security_notes = []
        
        # ---- Step 1: Security Check ----
        is_allowed, cleaned_message, notes = security.check_input(body.message)
        security_notes.extend(notes)
        
        if not is_allowed:
            logger.warning("Request blocked by security", 
                           extra={
                               "extra_data": {
                                   "reason": notes,
                                   "thread_id": body.thread_id,
                               }
                           })
            metrics.record_request(latency_ms=0, error=True)
            raise HTTPException(
                status_code=400, 
                detail="Your message was blocked by our security filters."
            )
        
        # ---- Step 2: Cache Lookup ----
        cached_response = cache.get(cleaned_message)
        if cached_response is not None:
            metrics.record_request(latency_ms=0, cache_hit=True)
            logger.info("Cache hit", extra={"extra_data": {
                "thread_id": body.thread_id
            }})
            return ChatResponse(
                response=cached_response,
                thread_id=body.thread_id,
                model_used="cache",
                cached=True,
                processing_time_ms=0,
            )