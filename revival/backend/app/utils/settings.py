# Why this exists: single source of truth for env-driven config so DEMO_MODE
# and secrets never leak into code paths by accident.
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    demo_mode: bool = True
    database_url: str = "sqlite:///./revival.db"
    cors_origins: str = "http://localhost:5174"

    anthropic_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_one_shot: str = ""
    stripe_price_monthly: str = ""

    calendly_webhook_secret: str = ""

    # Auth (M13). Supabase projects expose a shared JWT secret under
    # Project Settings → API → JWT Secret. Leave blank in DEMO_MODE.
    supabase_jwt_secret: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""

    # Jobber OAuth (M18). Register the app at https://developer.getjobber.com/
    # and use the `client credentials` + redirect URL from your app page.
    jobber_client_id: str = ""
    jobber_client_secret: str = ""
    jobber_redirect_uri: str = "http://localhost:5174/integrations/jobber/callback"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
