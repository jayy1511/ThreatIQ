from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Gemini API configuration
    # Prefer GEMINI_API_KEYS for multiple keys, fallback to GEMINI_API_KEY
    gemini_api_key: str = ""
    gemini_api_keys: str = ""
    
    mongodb_uri: str
    mongodb_db_name: str = "threatiq"
    
    firebase_project_id: str
    firebase_private_key: str
    firebase_client_email: str
    
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    frontend_url: str
    token_encryption_key: str
    
    cors_origins: str = "http://localhost:3000,http://localhost:8081,http://localhost:8082,http://localhost:19006,http://127.0.0.1:8081,http://127.0.0.1:8082"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Microservices
    analysis_service_url: str = "http://localhost:8010"
    analysis_service_api_key: str = ""
    
    environment: str = "development"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
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
