"""
Weather Service for getting UV index and weather conditions
"""
import random
from typing import Dict, Any, Optional


class WeatherService:
    """Simple weather service with mock data for now"""
    
    def get_weather(
        self, 
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: str = "US"
    ) -> Dict[str, Any]:
        """
        Get weather data for a location
        In production, this would call a real weather API
        """
        
        # Mock weather data for development
        # In production, integrate with OpenWeather API or similar
        return {
            "city": city or "Los Angeles",
            "state": state or "CA",
            "country": country,
            "temperature": random.randint(65, 85),
            "humidity": random.randint(40, 70),
            "uv_index": random.randint(3, 9),
            "conditions": random.choice(["Sunny", "Partly Cloudy", "Clear"]),
            "wind_speed": random.randint(5, 15),
            "feels_like": random.randint(65, 85)
        }