from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.middleware.auth import create_access_token, verify_password
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    if not verify_password(body.password, settings.admin_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )
    token, expiry = create_access_token()
    return LoginResponse(token=token, expires_at=expiry.isoformat())
