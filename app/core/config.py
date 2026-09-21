from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./carsharing.db"
    secret_key: str = Field(min_length=32)
    token_minutes: int = Field(default=120, ge=5, le=1440)
    cookie_secure: bool = False
    environment: Literal["development", "production"] = "development"
    allowed_hosts: list[str] = ["127.0.0.1", "localhost", "testserver"]

    @model_validator(mode="after")
    def production_settings(self):
        if self.environment == "production":
            if not self.cookie_secure:
                raise ValueError("Production requires COOKIE_SECURE=true and HTTPS")
            if not self.allowed_hosts or "*" in self.allowed_hosts:
                raise ValueError("Production requires explicit ALLOWED_HOSTS")
        return self


settings = Settings()
