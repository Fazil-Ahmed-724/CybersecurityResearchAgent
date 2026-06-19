from fastapi import APIRouter, HTTPException

from app.services.auth_service import AuthService
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    TokenResponse
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

auth_service = AuthService()


@router.post(
    "/register",
    response_model=UserResponse
)
def register_user(
    request: RegisterRequest
):

    try:

        user = auth_service.register_user(
            name=request.name,
            email=request.email,
            password=request.password
        )

        return UserResponse(
            id=user.id,
            name=user.name,
            email=user.email
        )

    except Exception as ex:

        raise HTTPException(
            status_code=400,
            detail=str(ex)
        )


@router.post(
    "/login",
    response_model=TokenResponse
)
def login_user(
    request: LoginRequest
):

    result = auth_service.login_user(
        email=request.email,
        password=request.password
    )

    if not result:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    return TokenResponse(
        access_token=result["access_token"],
        token_type=result["token_type"],
        user_id=result["user_id"],
        name=result["name"]
    )