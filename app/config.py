from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # App Settings
    app_name: str = "SkinSense AI"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Database
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "skinsense"
    
    # Redis
    redis_url: str = "redis://redis:6379"
    
    # JWT Settings
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # AI Services
    orbo_ai_api_key: str = ""
    orbo_api_key: str = ""  # Standard ORBO API key field
    orbo_ai_base_url: str = "https://api.orbo.ai"
    orbo_client_id: str = ""
    orbo_clientid: str = ""  # Legacy duplicate
    openai_api_key: str = ""
    perplexity_api_key: str = ""
    
    # AWS Settings
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket_name: str = "skinsense-images"
    cloudfront_domain: Optional[str] = None
    
    # Email Settings (for notifications)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    
    # ZeptoMail Settings
    zeptomail_send_token: str = ""
    zeptomail_host: str = "api.zeptomail.com"
    zeptomail_domain: str = "skinsense.app"
    
    # Subscription Settings
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    
    # Firebase Settings
    firebase_service_account_path: Optional[str] = None
    firebase_project_id: Optional[str] = None
    
    # Monitoring Settings
    prometheus_url: str = "http://localhost:9090"
    grafana_url: str = "http://localhost:3001"
    
    class Config:
        env_file = ".env"

settings = Settings()