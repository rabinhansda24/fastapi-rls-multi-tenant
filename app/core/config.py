from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "RLS FirstAPI"
    DEBUG: bool = False
    DATABASE_URL: str  # required — no default
    JWT_SECRET_KEY: str = Field(
        ...,
        validation_alias=AliasChoices("JWT_SECRET_KEY", "JWT_SECRET", "SECRET_KEY"),
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    CORS_ORIGINS: list[str] = []


    class Config:
        env_file = ".env"


settings = Settings()
