"""
Analysis Service Configuration
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Analysis service settings loaded from environment variables."""
    
    # Gemini API configuration
    gemini_api_key: str = ""
    gemini_api_keys: str = ""
    
    # Internal service authentication
    # Required in production; gateway must present this key via X-Internal-Service-Key header
    analysis_service_api_key: str = ""
    
    # Service configuration
    service_host: str = "0.0.0.0"
    service_port: int = 8010
    
    environment: str = "development"
    
    @property
    def gemini_keys_list(self) -> List[str]:
        """Parse Gemini API keys as a list."""
        if self.gemini_api_keys:
            return [k.strip() for k in self.gemini_api_keys.split(",") if k.strip()]
        if self.gemini_api_key:
            return [self.gemini_api_key]
        return []
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
