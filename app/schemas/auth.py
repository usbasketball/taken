from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"password": "changeme"}})

    password: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expires_at": "2026-04-15T12:00:00Z",
            }
        }
    )

    token: str
    expires_at: str  # ISO 8601 datetime string
