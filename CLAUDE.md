# Backend Context - SkinSense AI

<backend_context>
Python FastAPI backend with MongoDB, Redis caching, and AI service integrations. Deployed via GitHub CI/CD to AWS EC2 with zero-downtime blue-green deployment.
</backend_context>

## Architecture
- **API**: FastAPI with async endpoints
- **Database**: MongoDB with PyMongo (synchronous operations)
- **Caching**: Redis for recommendations and sessions
- **Storage**: AWS S3 for images
- **Tasks**: Celery for background processing

## Core Services

### AI Integration Services
- **ORBO Service**: Skin analysis with 10 metrics (0-100 scores)
- **OpenAI Service**: GPT-4 for personalized insights and feedback
- **Perplexity Service**: Real-time product search and recommendations
- **Recommendation Service**: Orchestrates all AI services

### Business Logic Services
- **Auth Service**: JWT authentication with FastAPI-Users
- **Subscription Service**: Free/Premium tier management
- **Goal Service**: AI-generated SMART goals and achievements
- **Notification Service**: FCM push notifications

## Database Schema

### CRITICAL: ObjectId Usage
```python
# ALWAYS convert user_id to ObjectId before database operations
from bson import ObjectId

# ✅ CORRECT - Always use ObjectId for user_id
user_oid = ObjectId(user_id_string)
db.collection.find({"user_id": user_oid})

# ❌ WRONG - Never store user_id as string
db.collection.find({"user_id": "68b5c43842613c871ab5a236"})

# Standard conversion pattern for all services:
try:
    user_oid = ObjectId(user_id)
except:
    raise ValueError(f"Invalid user_id format: {user_id}")
```

### Core Collections
```python
# Users
{
  "_id": ObjectId,  # Primary key
  "email": str,
  "subscription": {
    "tier": "free|premium",
    "usage": {"monthly_scans_used": int, "daily_pal_questions_used": int}
  }
}

# Skin Analyses  
{
  "user_id": ObjectId,  # ALWAYS ObjectId, never string
  "orbo_response": {"overall_skin_health_score": int, "hydration": int, ...},
  "ai_feedback": str,
  "image_url": str
}

# Goals
{
  "user_id": ObjectId,  # ALWAYS ObjectId, never string
  "title": str,
  "target_metric": str,
  "progress": float,
  "milestones": [{"percentage": int, "completed": bool}]
}

# User Achievements
{
  "user_id": ObjectId,  # ALWAYS ObjectId, never string
  "achievement_id": str,
  "is_unlocked": bool,
  "progress": float,
  "unlocked_at": datetime
}
```

## Key Patterns

### Database Operations
```python
# Use PyMongo (NOT Motor - deprecated 2026)
from pymongo import MongoClient
client = MongoClient(settings.mongodb_url)
db = client.get_database()

# Async endpoints with sync DB calls
@router.post("/analysis/")
async def create_analysis(data: AnalysisCreate):
    result = db.analyses.insert_one(data.dict())
    return {"id": str(result.inserted_id)}
```

### AI Service Integration
```python
# Error handling with fallbacks
try:
    orbo_result = await orbo_service.analyze_image(image)
    ai_feedback = await openai_service.generate_feedback(orbo_result)
    recommendations = await perplexity_service.get_products(orbo_result)
except Exception as e:
    logger.error(f"AI service error: {e}")
    return fallback_response()
```

### Subscription Limits
```python
# Check limits before processing
usage_check = SubscriptionService.check_scan_limit(user)
if not usage_check["allowed"]:
    raise HTTPException(400, "Scan limit reached")
    
# Increment after successful operation
SubscriptionService.increment_scan_usage(user)
```

## Environment Variables
```bash
# Database
MONGODB_URL=mongodb+srv://...

# AI Services
ORBO_AI_API_KEY=your-orbo-key
OPENAI_API_KEY=sk-proj-...
PERPLEXITY_API_KEY=pplx-...

# AWS
AWS_ACCESS_KEY_ID=...
S3_BUCKET_NAME=...

# Security
SECRET_KEY=...
```

## Deployment Rules

<critical_deployment>
NEVER deploy manually to EC2. All deployments MUST go through GitHub CI/CD pipeline.
</critical_deployment>

### Deployment Process
1. **Local Development**: Test with `docker-compose up --build`
2. **Code Quality**: Run `black .` and `flake8` before commit
3. **GitHub Push**: `git push origin main` triggers automatic deployment
4. **Zero-Downtime**: Blue-green deployment with nginx load balancer
5. **Health Checks**: Automatic rollback if deployment fails

### Docker Configuration
```yaml
# docker-compose.yml
services:
  backend:
    build: .
    environment:
      - MONGODB_URL=${MONGODB_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - .:/app
    ports:
      - "8000:8000"
```

## API Standards

### Endpoint Patterns
- **Auth**: `/api/v1/auth/*`
- **Analysis**: `/api/v1/analysis/*`
- **Subscription**: `/api/v1/subscription/*`
- **Goals**: `/api/v1/goals/*`

### Response Format
```python
# Success
{"status": "success", "data": {...}}

# Error
{"status": "error", "message": "...", "code": "ERROR_CODE"}

# Pagination
{"data": [...], "total": int, "page": int, "per_page": int}
```

### Error Handling
```python
# Custom exceptions
class SubscriptionLimitError(HTTPException):
    def __init__(self):
        super().__init__(400, "Subscription limit reached")

# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse({"error": "Internal server error"}, 500)
```

## Code Quality Standards

### Python Formatting
```bash
# Required before commit
black .                 # Auto-format code
flake8                 # Check style issues
pytest                 # Run tests (when available)
```

### FastAPI Best Practices
- Use Pydantic models for request/response validation
- Implement dependency injection for database connections
- Add comprehensive error handling
- Document all endpoints with OpenAPI schemas
- Use async/await for I/O operations

<prohibited_backend_actions>
- Using Motor AsyncIOMotorClient (use PyMongo instead)
- Manual EC2 deployment or SSH access
- Committing environment variables or secrets
- Skipping error handling in API endpoints
- Using synchronous libraries in async endpoints without proper wrapping
</prohibited_backend_actions>

## Monitoring & Debugging
- **Logs**: Check with `docker logs skinsense_backend`
- **Health**: GET `/health` endpoint with database status
- **API Docs**: Available at `/docs` (Swagger UI)
- **Deployment**: Monitor at GitHub Actions page

## Common Issues
1. **Database Connection**: Check MONGODB_URL format and network access
2. **AI Service Limits**: Monitor API usage and implement proper fallbacks
3. **Memory Usage**: Profile endpoints with large image processing
4. **Subscription Logic**: Ensure usage counters reset properly
