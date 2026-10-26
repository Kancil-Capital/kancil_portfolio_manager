from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"), env_file_encoding="utf-8", extra="ignore"
    )

    supabase_url: str = ""
    supabase_secret_key: str = ""
    supabase_jwt_secret: str = ""
    alpha_vantage_api_key: str = ""

    cors_origins: list[str] = ["http://localhost:3000"]

    # Path to trained XGBoost model (relative to backend/ dir)
    pead_model_path: str = "../models/pead_model.joblib"


settings = Settings()
