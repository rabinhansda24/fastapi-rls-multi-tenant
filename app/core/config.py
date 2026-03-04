from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "RLS FirstAPI"
    DEBUG: bool = False
    DATABASE_URL: str = "sqlite:///./test.db"
    JWT_SECRET_KEY: str = "your_secret_key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30


    class Config:
        env_file = ".env"


settings = Settings()