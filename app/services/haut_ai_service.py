import httpx
import asyncio
from typing import Dict, Any, Optional
from PIL import Image
from io import BytesIO
import base64
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class HautAIService:
    def __init__(self):
        self.api_key = settings.haut_ai_api_key
        self.base_url = settings.haut_ai_base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def analyze_skin(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Analyze skin using Haut.ai API
        """
        try:
            # Preprocess image
            processed_image = await self.preprocess_image(image_bytes)
            
            # Convert to base64
            image_b64 = base64.b64encode(processed_image).decode('utf-8')
            
            # Make API call
            response = await self._make_api_request(image_b64)
            
            # Parse response
            return self._parse_analysis_result(response)
            
        except Exception as e:
            logger.error(f"Haut.ai analysis failed: {e}")
            raise
    
    async def preprocess_image(self, image_bytes: bytes) -> bytes:
        """
        Preprocess image for optimal analysis
        """
        try:
            image = Image.open(BytesIO(image_bytes))
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize if too large (max 1024x1024)
            max_size = 1024
            if max(image.size) > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Enhance image quality
            # You can add more preprocessing here
            
            # Convert back to bytes
            buffer = BytesIO()
            image.save(buffer, format='JPEG', quality=90)
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            raise
    
    async def _make_api_request(self, image_b64: str) -> Dict[str, Any]:
        """
        Make request to Haut.ai API
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "image": f"data:image/jpeg;base64,{image_b64}",
            "analysis_type": "full",  # or specific analysis types
            "return_confidence": True
        }
        
        response = await self.client.post(
            f"{self.base_url}/analyze",
            headers=headers,
            json=payload
        )
        
        response.raise_for_status()
        return response.json()
    
    def _parse_analysis_result(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and structure Haut.ai response
        """
        try:
            # Extract key metrics (adjust based on actual Haut.ai response structure)
            analysis_data = {
                "skin_type": response.get("skin_type", "unknown"),
                "concerns": response.get("concerns", []),
                "scores": {
                    "hydration": response.get("hydration_score", 0.0),
                    "texture": response.get("texture_score", 0.0),
                    "tone_evenness": response.get("tone_score", 0.0),
                    "clarity": response.get("clarity_score", 0.0),
                    "overall": response.get("overall_score", 0.0)
                },
                "confidence": response.get("confidence", 0.0),
                "raw_response": response
            }
            
            return analysis_data
            
        except Exception as e:
            logger.error(f"Failed to parse Haut.ai response: {e}")
            return {
                "skin_type": "unknown",
                "concerns": [],
                "scores": {},
                "confidence": 0.0,
                "raw_response": response
            }
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Global instance
haut_ai_service = HautAIService()