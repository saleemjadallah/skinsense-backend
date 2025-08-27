from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.database import connect_to_mongo, close_mongo_connection, db
from app.core.redis import get_redis, close_redis
from app.api.v1 import auth, users, skin_analysis, products, community, routines, notifications, goals, plans, monitoring, learning, insights, homepage_optimized, pal, achievements
from app.api.v1.endpoints import calendar, reminders
from app.core.monitoring import setup_metrics  # track_active_users

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting SkinSense AI Backend...")
    connect_to_mongo()  # Now synchronous
    get_redis()  # Initialize Redis connection
    
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    close_mongo_connection()  # Now synchronous
    close_redis()  # Close Redis connection
    logger.info("Application shutdown complete")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="SkinSense AI - Beauty Tech Companion Backend API",
    lifespan=lifespan
)

# Set up Prometheus metrics - temporarily disabled for debugging
# instrumentator = setup_metrics(app)
# instrumentator.instrument(app).expose(app, endpoint="/metrics")

# CORS middleware
# CORS configuration - Allow all origins for mobile apps
# Mobile apps (iOS/Android) don't send Origin headers like web apps
cors_origins = ["*"]  # Allow all origins for mobile app compatibility

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Page", "X-Per-Page"],
    max_age=3600,
)

# Trusted host middleware
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["api.skinsense.app", "*.skinsense.app", "api.skinsense.ai", "*.skinsense.ai", "56.228.12.81", "localhost"]
    )

# Add middleware for tracking active users

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(skin_analysis.router, prefix="/api/v1/analysis", tags=["Skin Analysis"])
app.include_router(products.router, prefix="/api/v1/products", tags=["Products"])
app.include_router(community.router, prefix="/api/v1/community", tags=["Community"])
app.include_router(routines.router, prefix="/api/v1/routines", tags=["Routines"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(goals.router, prefix="/api/v1/goals", tags=["Goals"])
app.include_router(achievements.router, prefix="/api/v1", tags=["Achievements"])
app.include_router(plans.router, prefix="/api/v1", tags=["Plans"])
app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["Monitoring"])
app.include_router(learning.router, prefix="/api/v1/learning", tags=["Learning"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["Insights"])
app.include_router(reminders.router, prefix="/api/v1/reminders", tags=["Smart Reminders"])
app.include_router(calendar.router, prefix="/api/v1/calendar", tags=["Calendar"])
app.include_router(homepage_optimized.router, prefix="/api/v1", tags=["Optimized"])
app.include_router(pal.router, prefix="/api/v1", tags=["Pal AI Assistant"])

# Test endpoints removed - was causing import issues

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Check database connection
    db_status = "connected" if db.database is not None else "disconnected"
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": "development" if settings.DEBUG else "production",
        "database": db_status,
        "mongodb_url_set": bool(settings.MONGODB_URL),
        "database_name": settings.DATABASE_NAME if settings.DATABASE_NAME else "not_set"
    }

# Root endpoint
# Monitoring endpoint
@app.get("/monitoring")
async def monitoring_info():
    """Monitoring information"""
    return {
        "message": "SkinSense AI Monitoring",
        "dashboard_url": "/api/v1/monitoring/dashboard",
        "metrics_url": "/metrics",
        "health_url": "/api/v1/monitoring/health/detailed",
        "note": "Dashboard requires admin authentication",
        "grafana_dashboards": [
            "Overview Dashboard",
            "API Performance",
            "AI Services Monitoring",
            "Business Metrics"
        ]
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to SkinSense AI Backend",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )