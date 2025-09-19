from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "SkinSense AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    BASE_URL: str = os.getenv("BASE_URL", "https://api.skinsense.app")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017/skinsense")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "skinpal")  # Using skinpal as per the MongoDB URL
    
    # AWS S3
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "skinsense-images")
    
    # ORBO AI Configuration
    ORBO_BASE_URL: str = "https://api.gateway.orbo.ai/demo/supertouch/skin/v1/"
    ORBO_CLIENT_ID: str = os.getenv("ORBO_CLIENT_ID", "")
    ORBO_API_KEY: str = os.getenv("ORBO_API_KEY", "")
    # Legacy names for ORBO (for backward compatibility)
    ORBO_AI_API_KEY: str = os.getenv("ORBO_AI_API_KEY", "")
    ORBO_CLIENTID: str = os.getenv("ORBO_CLIENTID", "")
    
    # CloudFront CDN
    CLOUDFRONT_DOMAIN: str = os.getenv("CLOUDFRONT_DOMAIN", "")
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Perplexity
    PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY", "")
    
    # ZeptoMail Email Service
    ZEPTOMAIL_SEND_TOKEN: Optional[str] = os.getenv("ZEPTOMAIL_SEND_TOKEN")
    ZEPTOMAIL_HOST: Optional[str] = os.getenv("ZEPTOMAIL_HOST", "api.zeptomail.com")
    ZEPTOMAIL_DOMAIN: Optional[str] = os.getenv("ZEPTOMAIL_DOMAIN", "skinsense.app")
    
    # Email (optional SMTP)
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: Optional[int] = int(os.getenv("SMTP_PORT", 587)) if os.getenv("SMTP_PORT") else 587
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    FROM_EMAIL: Optional[str] = os.getenv("FROM_EMAIL", "noreply@skinsense.ai")
    
    # Stripe Payment
    STRIPE_SECRET_KEY: Optional[str] = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    # Firebase
    FIREBASE_SERVICE_ACCOUNT_PATH: Optional[str] = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    FIREBASE_PROJECT_ID: Optional[str] = os.getenv("FIREBASE_PROJECT_ID")
    
    # Monitoring
    PROMETHEUS_URL: Optional[str] = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    GRAFANA_URL: Optional[str] = os.getenv("GRAFANA_URL", "http://localhost:3001")
    
    # Redis (for caching and background tasks)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # CORS
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Allow extra fields from .env file

settings = Settings()

# Validate critical settings for production
if not settings.DEBUG:
    if not settings.SECRET_KEY:
        raise ValueError("SECRET_KEY must be set in production environment")
    if settings.SECRET_KEY == "your-secret-key-here-change-in-production":
        raise ValueError("Default SECRET_KEY detected in production - please set a secure key")
    if len(settings.SECRET_KEY) < 32:
        raise ValueError("SECRET_KEY should be at least 32 characters for security")