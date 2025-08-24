from prometheus_client import Counter, Histogram, Gauge, Info as PrometheusInfo
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from prometheus_fastapi_instrumentator.metrics import Info as MetricsInfo
import time
from typing import Callable
from fastapi import FastAPI, Request, Response
from functools import wraps

# Custom metrics for AI services
ai_service_requests = Counter(
    'ai_service_requests_total',
    'Total requests to AI services',
    ['service', 'endpoint', 'status']
)

ai_service_duration = Histogram(
    'ai_service_duration_seconds',
    'Duration of AI service requests',
    ['service', 'endpoint']
)

ai_service_tokens = Counter(
    'ai_service_tokens_total',
    'Total tokens used by AI services',
    ['service', 'type']  # type: prompt/completion
)

# Skin analysis metrics
skin_analysis_total = Counter(
    'skin_analysis_total',
    'Total skin analyses performed',
    ['user_type']  # new/returning
)

skin_analysis_score = Histogram(
    'skin_analysis_score',
    'Distribution of skin health scores',
    buckets=(0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
)

# Product recommendation metrics
recommendations_generated = Counter(
    'recommendations_generated_total',
    'Total product recommendations generated',
    ['source']  # cache/fresh
)

recommendation_cache_hits = Counter(
    'recommendation_cache_hits_total',
    'Cache hits for recommendations'
)

# User activity metrics
active_users = Gauge(
    'active_users_current',
    'Current number of active users'
)

routine_completions = Counter(
    'routine_completions_total',
    'Total routine completions',
    ['routine_type']  # morning/evening/weekly
)

# Database metrics
db_operations = Counter(
    'mongodb_operations_total',
    'Total MongoDB operations',
    ['operation', 'collection', 'status']
)

db_operation_duration = Histogram(
    'mongodb_operation_duration_seconds',
    'Duration of MongoDB operations',
    ['operation', 'collection']
)

# Business metrics
api_revenue = Counter(
    'api_revenue_cents',
    'Estimated API costs in cents',
    ['service']
)

# App info
app_info = PrometheusInfo('app_info', 'Application information')
app_info.info({
    'version': '1.0.0',
    'name': 'SkinSense AI Backend',
    'environment': 'production'
})

def setup_metrics(app: FastAPI) -> Instrumentator:
    """
    Set up Prometheus metrics for FastAPI application
    """
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health"],
        inprogress_name="fastapi_inprogress",
        inprogress_labels=True,
    )
    
    # Add default metrics
    instrumentator.add(
        metrics.latency(
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
        )
    )
    instrumentator.add(metrics.request_size())
    instrumentator.add(metrics.response_size())
    instrumentator.add(metrics.requests())
    
    # Custom metric for slow requests
    @instrumentator.add
    def slow_requests(info: MetricsInfo) -> None:
        if not hasattr(slow_requests, '_counter'):
            slow_requests._counter = Counter(
                name="slow_requests_total",
                documentation="Total number of slow requests (>1s)",
                labelnames=("method", "handler"),
            )
        
        if info.modified_duration > 1:
            slow_requests._counter.labels(
                method=info.method,
                handler=info.modified_handler
            ).inc()
    
    # Error rate by endpoint
    @instrumentator.add
    def error_rate(info: MetricsInfo) -> None:
        if not hasattr(error_rate, '_counter'):
            error_rate._counter = Counter(
                name="http_errors_total",
                documentation="Total number of HTTP errors",
                labelnames=("method", "handler", "status"),
            )
        
        if str(info.modified_status).startswith(("4", "5")):
            error_rate._counter.labels(
                method=info.method,
                handler=info.modified_handler,
                status=str(info.modified_status)
            ).inc()
    
    return instrumentator

def track_ai_service(service: str, endpoint: str):
    """
    Decorator to track AI service metrics (handles both sync and async functions)
    """
    import inspect
    
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            # For async functions
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                status = "success"
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    status = "error"
                    raise
                finally:
                    duration = time.time() - start_time
                    ai_service_requests.labels(service=service, endpoint=endpoint, status=status).inc()
                    ai_service_duration.labels(service=service, endpoint=endpoint).observe(duration)
                    
                    # Track estimated costs
                    if service == "openai":
                        api_revenue.labels(service=service).inc(int(duration * 0.1))  # Rough estimate
                    elif service == "perplexity":
                        api_revenue.labels(service=service).inc(5)  # 5 cents per request estimate
            
            return async_wrapper
        else:
            # For sync functions
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                status = "success"
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    status = "error"
                    raise
                finally:
                    duration = time.time() - start_time
                    ai_service_requests.labels(service=service, endpoint=endpoint, status=status).inc()
                    ai_service_duration.labels(service=service, endpoint=endpoint).observe(duration)
                    
                    # Track estimated costs
                    if service == "openai":
                        api_revenue.labels(service=service).inc(int(duration * 0.1))  # Rough estimate
                    elif service == "perplexity":
                        api_revenue.labels(service=service).inc(5)  # 5 cents per request estimate
            
            return sync_wrapper
    return decorator

def track_db_operation(operation: str, collection: str):
    """
    Decorator to track MongoDB operations
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                db_operations.labels(
                    operation=operation,
                    collection=collection,
                    status=status
                ).inc()
                db_operation_duration.labels(
                    operation=operation,
                    collection=collection
                ).observe(duration)
                
        return wrapper
    return decorator

# Middleware for tracking active users
async def track_active_users(request: Request, call_next):
    """
    Middleware to track active users based on JWT tokens
    """
    # This is a simplified version - in production, you'd decode JWT
    # and track unique user IDs
    active_users.inc()
    
    try:
        response = await call_next(request)
        return response
    finally:
        active_users.dec()