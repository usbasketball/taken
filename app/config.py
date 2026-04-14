from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./test.db"
    admin_password: str = "changeme"
    jwt_secret: str = "insecure-dev-secret-change-in-production"
    jwt_expire_days: int = 7
    api_key: str = ""
    auth0_domain: str = ""
    auth0_audience: str = ""
    foys_federation_id: str = "52cfa65e-9782-4a81-ab35-e2f981fcb7a9"
    foys_home_org_id: str = "2f1e5e8e-e2c5-4d8b-9d21-1584bc6c8d5a"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
