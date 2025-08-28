import logging
import random
import string
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import httpx
from app.core.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.send_token = settings.ZEPTOMAIL_SEND_TOKEN
        self.api_url = f"https://{settings.ZEPTOMAIL_HOST}/v1.1/email"
        self.from_email = f"noreply@{settings.ZEPTOMAIL_DOMAIN}"
        self.from_name = settings.APP_NAME
        
        # OTP storage (in production, use Redis)
        self.otp_storage: Dict[str, Dict] = {}
    
    def generate_otp(self, length: int = 6) -> str:
        """Generate a random OTP code"""
        return ''.join(random.choices(string.digits, k=length))
    
    def store_otp(self, email: str, otp: str, purpose: str = "verification") -> None:
        """Store OTP with expiration (15 minutes)"""
        redis_client = get_redis()
        redis_key = f"otp:{email}:{purpose}"
        memory_key = f"{email}:{purpose}"
        
        if redis_client:
            try:
                # Use Redis with 15-minute TTL
                data = {
                    "otp": otp,
                    "attempts": 0
                }
                redis_client.setex(redis_key, 900, json.dumps(data))  # 900 seconds = 15 minutes
                logger.info(f"OTP stored in Redis for {email}, purpose: {purpose}, key: {redis_key}")
            except Exception as e:
                logger.error(f"Failed to store OTP in Redis: {e}")
                # Fallback to in-memory storage
                self.otp_storage[memory_key] = {
                    "otp": otp,
                    "expires_at": datetime.utcnow() + timedelta(minutes=15),
                    "attempts": 0
                }
                logger.info(f"OTP stored in memory fallback for {email}, purpose: {purpose}")
        else:
            # Fallback to in-memory storage
            self.otp_storage[memory_key] = {
                "otp": otp,
                "expires_at": datetime.utcnow() + timedelta(minutes=15),
                "attempts": 0
            }
            logger.info(f"OTP stored in memory for {email}, purpose: {purpose}, OTP: {otp}")
    
    def verify_otp(self, email: str, otp: str, purpose: str = "verification") -> bool:
        """Verify OTP code"""
        redis_client = get_redis()
        redis_key = f"otp:{email}:{purpose}"
        memory_key = f"{email}:{purpose}"
        
        logger.info(f"Verifying OTP for {email}, purpose: {purpose}, Redis available: {redis_client is not None}")
        logger.info(f"In-memory OTP storage keys: {list(self.otp_storage.keys())}")
        
        if redis_client:
            try:
                # Try Redis first
                stored_json = redis_client.get(redis_key)
                if not stored_json:
                    logger.warning(f"No OTP found in Redis for {redis_key}")
                    # Check in-memory fallback
                    if memory_key in self.otp_storage:
                        logger.info(f"Found OTP in memory fallback for {memory_key}")
                        return self._verify_memory_otp(memory_key, otp)
                    return False
                
                stored_data = json.loads(stored_json)
                logger.info(f"Found OTP in Redis for {email}")
                
                # Check attempts (max 3)
                if stored_data["attempts"] >= 3:
                    redis_client.delete(redis_key)
                    logger.warning(f"Max attempts exceeded for {email}")
                    return False
                
                # Verify OTP
                if stored_data["otp"] == otp:
                    redis_client.delete(redis_key)
                    logger.info(f"OTP verified successfully for {email}")
                    return True
                
                # Increment attempts
                stored_data["attempts"] += 1
                redis_client.setex(redis_key, redis_client.ttl(redis_key), json.dumps(stored_data))
                logger.warning(f"Invalid OTP for {email}, attempts: {stored_data['attempts']}")
                return False
            except Exception as e:
                logger.error(f"Redis error during OTP verification: {e}")
                # Fallback to in-memory
                if memory_key in self.otp_storage:
                    logger.info(f"Falling back to memory storage for {memory_key}")
                    return self._verify_memory_otp(memory_key, otp)
                return False
        else:
            # Fallback to in-memory storage
            logger.info(f"Using in-memory storage for OTP verification")
            return self._verify_memory_otp(memory_key, otp)
    
    def _verify_memory_otp(self, memory_key: str, otp: str) -> bool:
        """Verify OTP from in-memory storage"""
        if memory_key not in self.otp_storage:
            logger.warning(f"No OTP found in memory for {memory_key}")
            return False
        
        stored_data = self.otp_storage[memory_key]
        
        # Check if OTP expired
        if datetime.utcnow() > stored_data["expires_at"]:
            del self.otp_storage[memory_key]
            logger.warning(f"OTP expired for {memory_key}")
            return False
        
        # Check attempts (max 3)
        if stored_data["attempts"] >= 3:
            del self.otp_storage[memory_key]
            logger.warning(f"Max attempts exceeded for {memory_key}")
            return False
        
        # Verify OTP
        if stored_data["otp"] == otp:
            del self.otp_storage[memory_key]
            logger.info(f"OTP verified successfully from memory for {memory_key}")
            return True
        
        # Increment attempts
        stored_data["attempts"] += 1
        logger.warning(f"Invalid OTP for {memory_key}, attempts: {stored_data['attempts']}")
        return False
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send email using ZeptoMail API"""
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self.send_token
        }
        
        payload = {
            "from": {
                "address": self.from_email,
                "name": self.from_name
            },
            "to": [
                {
                    "email_address": {
                        "address": to_email
                    }
                }
            ],
            "subject": subject,
            "htmlbody": html_content
        }
        
        if text_content:
            payload["textbody"] = text_content
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"Email sent successfully to {to_email}")
                    return True
                else:
                    logger.error(f"Failed to send email: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    def send_otp_email_sync(self, to_email: str, username: str) -> str:
        """Synchronous wrapper for send_otp_email for background tasks"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.send_otp_email(to_email, username))
    
    async def send_otp_email(self, to_email: str, username: str) -> str:
        """Send OTP verification email"""
        otp = self.generate_otp()
        self.store_otp(to_email, otp, "verification")
        
        subject = f"{settings.APP_NAME} - Verify Your Email"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #E91E63 0%, #FF4081 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .content {{
                    background: #fff;
                    padding: 30px;
                    border: 1px solid #ddd;
                    border-top: none;
                    border-radius: 0 0 10px 10px;
                }}
                .otp-code {{
                    background: #FCE4EC;
                    color: #E91E63;
                    font-size: 32px;
                    font-weight: bold;
                    text-align: center;
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px 0;
                    letter-spacing: 5px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{settings.APP_NAME}</h1>
                <p>Your Personalized Skincare Journey Starts Here</p>
            </div>
            <div class="content">
                <h2>Hi {username},</h2>
                <p>Welcome to {settings.APP_NAME}! To complete your registration, please verify your email address using the code below:</p>
                
                <div class="otp-code">{otp}</div>
                
                <p>This code will expire in 15 minutes for security reasons.</p>
                
                <p>If you didn't create an account with {settings.APP_NAME}, please ignore this email.</p>
                
                <p>Need help? Contact our support team at support@{settings.ZEPTOMAIL_DOMAIN}</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 {settings.APP_NAME}. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Hi {username},
        
        Welcome to {settings.APP_NAME}! Your verification code is: {otp}
        
        This code will expire in 15 minutes.
        
        If you didn't create an account, please ignore this email.
        
        Best regards,
        The {settings.APP_NAME} Team
        """
        
        # Log OTP for testing when email fails
        logger.info(f"OTP for {to_email}: {otp}")
        
        result = await self.send_email(to_email, subject, html_content, text_content)
        if not result:
            logger.warning(f"Failed to send OTP email to {to_email}, but OTP {otp} is stored and can be used")
        
        return otp
    
    async def send_password_reset_email(self, to_email: str, username: str) -> str:
        """Send password reset OTP email"""
        otp = self.generate_otp()
        self.store_otp(to_email, otp, "reset")
        
        subject = f"{settings.APP_NAME} - Reset Your Password"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #E91E63 0%, #FF4081 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .content {{
                    background: #fff;
                    padding: 30px;
                    border: 1px solid #ddd;
                    border-top: none;
                    border-radius: 0 0 10px 10px;
                }}
                .otp-code {{
                    background: #FCE4EC;
                    color: #E91E63;
                    font-size: 32px;
                    font-weight: bold;
                    text-align: center;
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px 0;
                    letter-spacing: 5px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{settings.APP_NAME}</h1>
                <p>Password Reset Request</p>
            </div>
            <div class="content">
                <h2>Hi {username},</h2>
                <p>We received a request to reset your password. Use the code below to complete the process:</p>
                
                <div class="otp-code">{otp}</div>
                
                <p>This code will expire in 15 minutes for security reasons.</p>
                
                <p>If you didn't request a password reset, please ignore this email and your password will remain unchanged.</p>
                
                <p>For security reasons, we recommend:</p>
                <ul>
                    <li>Using a strong, unique password</li>
                    <li>Not sharing your password with anyone</li>
                    <li>Enabling two-factor authentication</li>
                </ul>
            </div>
            <div class="footer">
                <p>&copy; 2024 {settings.APP_NAME}. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Hi {username},
        
        We received a request to reset your password. Your reset code is: {otp}
        
        This code will expire in 15 minutes.
        
        If you didn't request this, please ignore this email.
        
        Best regards,
        The {settings.APP_NAME} Team
        """
        
        # Log OTP for testing when email fails
        logger.info(f"OTP for {to_email}: {otp}")
        
        result = await self.send_email(to_email, subject, html_content, text_content)
        if not result:
            logger.warning(f"Failed to send OTP email to {to_email}, but OTP {otp} is stored and can be used")
        
        return otp
    
    def send_welcome_email_sync(self, to_email: str, username: str) -> bool:
        """Synchronous wrapper for send_welcome_email for background tasks"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.send_welcome_email(to_email, username))
    
    async def send_welcome_email(self, to_email: str, username: str) -> bool:
        """Send welcome email after successful registration"""
        subject = f"Welcome to {settings.APP_NAME} - Your Skincare Journey Begins!"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #E91E63 0%, #FF4081 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .content {{
                    background: #fff;
                    padding: 30px;
                    border: 1px solid #ddd;
                    border-top: none;
                    border-radius: 0 0 10px 10px;
                }}
                .feature {{
                    display: flex;
                    align-items: center;
                    margin: 20px 0;
                    padding: 15px;
                    background: #FDF7FA;
                    border-radius: 10px;
                }}
                .feature-icon {{
                    font-size: 30px;
                    margin-right: 15px;
                }}
                .cta-button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #E91E63 0%, #FF4081 100%);
                    color: white;
                    padding: 15px 30px;
                    text-decoration: none;
                    border-radius: 30px;
                    font-weight: bold;
                    margin: 20px auto;
                    text-align: center;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Welcome to {settings.APP_NAME}!</h1>
                <p>Your Personalized Skincare Journey Starts Now</p>
            </div>
            <div class="content">
                <h2>Hi {username},</h2>
                <p>We're thrilled to have you join the {settings.APP_NAME} community! You've taken the first step towards achieving your best skin ever.</p>
                
                <h3>Here's what you can do with {settings.APP_NAME}:</h3>
                
                <div class="feature">
                    <span class="feature-icon">📸</span>
                    <div>
                        <strong>AI Skin Analysis</strong><br>
                        Get detailed insights about your skin health with our advanced AI technology
                    </div>
                </div>
                
                <div class="feature">
                    <span class="feature-icon">🎯</span>
                    <div>
                        <strong>Personalized Recommendations</strong><br>
                        Receive product suggestions tailored to your unique skin needs
                    </div>
                </div>
                
                <div class="feature">
                    <span class="feature-icon">📅</span>
                    <div>
                        <strong>Custom Routines</strong><br>
                        Build and track your perfect morning and evening skincare routines
                    </div>
                </div>
                
                <div class="feature">
                    <span class="feature-icon">📊</span>
                    <div>
                        <strong>Progress Tracking</strong><br>
                        Monitor your skin's improvement over time with detailed analytics
                    </div>
                </div>
                
                <center>
                    <a href="skinsense://home" class="cta-button">Start Your First Analysis</a>
                </center>
                
                <p><strong>Pro Tips to Get Started:</strong></p>
                <ol>
                    <li>Take your first skin analysis photo in good lighting</li>
                    <li>Set up your daily routine reminders</li>
                    <li>Join our community to connect with skincare enthusiasts</li>
                    <li>Track your progress weekly for best results</li>
                </ol>
                
                <p>If you have any questions, our support team is here to help at support@{settings.ZEPTOMAIL_DOMAIN}</p>
            </div>
            <div class="footer">
                <p>Follow us on social media for skincare tips and updates!</p>
                <p>&copy; 2024 {settings.APP_NAME}. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Hi {username},
        
        Welcome to {settings.APP_NAME}!
        
        We're thrilled to have you join our community. You've taken the first step towards achieving your best skin ever.
        
        What you can do with {settings.APP_NAME}:
        - AI Skin Analysis for detailed insights
        - Personalized product recommendations
        - Custom skincare routines
        - Progress tracking over time
        
        Get started by taking your first skin analysis photo!
        
        Best regards,
        The {settings.APP_NAME} Team
        """
        
        return await self.send_email(to_email, subject, html_content, text_content)


# Create singleton instance
email_service = EmailService()