from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.auth import verify_password, create_access_token
from app.config import APP_USERNAME, APP_PASSWORD_HASH

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


@router.post("/api/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """
    Validate credentials and return a JWT.

    Note: we check username AND run verify_password even if the username is
    wrong. This prevents timing attacks — an attacker can't tell whether the
    username or the password was wrong from how fast the server responds.
    """
    valid = (
        body.username == APP_USERNAME
        and APP_PASSWORD_HASH is not None
        and verify_password(body.password, APP_PASSWORD_HASH)
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token(data={"sub": body.username})
    return {"access_token": token, "token_type": "bearer"}