from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    PROJECT_NAME: str = "SortMyPlate"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/v1"
    
    # Security & JWT
    SECRET_KEY: str = "sortmyplate-ultra-secure-key-256bit-aes-gcm-master-key-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    # Database Settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./sortmyplate.db"
    
    # Google Sign-In & OAuth 2.0
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""
    
    # LLM Settings
    LLM_PROVIDER: Literal["mock", "deepseek", "claude", "openai"] = "mock"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()
