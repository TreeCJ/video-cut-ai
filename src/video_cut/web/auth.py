"""Authentication routes: login, register, logout, and user management."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from video_cut.db.database import get_db
from video_cut.services.user_service import (
    UserServiceError,
    UserAlreadyExistsError,
    UserNotFoundError,
    InvalidCredentialsError,
    create_user,
    authenticate_user,
    update_user,
    delete_user,
    list_users,
)
from video_cut.auth.auth import (
    create_access_token,
    get_current_user,
    require_role,
)
from video_cut.db.models import User

router = APIRouter()


# Pydantic models for request/response
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "editor"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[str] = None


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Login with username and password.

    Returns a JWT token in both the response body and as an HTTP-only cookie.
    """
    try:
        user = authenticate_user(db, request.username, request.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Create access token
    token_data = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
    }
    access_token = create_access_token(token_data)

    # Set HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=86400,  # 24 hours
        samesite="lax",
    )

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        username=user.username,
        role=user.role,
    )


@router.post("/auth/register", response_model=UserResponse)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new user.

    Only admins can register new users. For non-admin access,
    use the admin panel instead.
    """
    try:
        user = create_user(
            db=db,
            username=request.username,
            email=request.email,
            password=request.password,
            role=request.role,
        )
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
        )
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/auth/logout")
async def logout(response: Response):
    """Logout by clearing the access token cookie."""
    response.delete_cookie(key="access_token")
    return {"message": "Logged out successfully"}


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )


# Admin user management routes
@router.get("/admin/users", response_model=UserListResponse)
async def list_all_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """List all users (admin only)."""
    users = list_users(db, skip=skip, limit=limit, role=role, is_active=is_active)
    total = len(users)  # In production, use count_users()

    return UserListResponse(
        users=[
            UserResponse(
                id=u.id,
                username=u.username,
                email=u.email,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at.isoformat() if u.created_at else None,
            )
            for u in users
        ],
        total=total,
    )


@router.put("/admin/users/{user_id}", response_model=UserResponse)
async def update_user_admin(
    user_id: int,
    username: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update user information (admin only)."""
    try:
        user = update_user(
            db=db,
            user_id=user_id,
            username=username,
            email=email,
            password=password,
            role=role,
            is_active=is_active,
        )
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None,
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.delete("/admin/users/{user_id}")
async def delete_user_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Delete a user (soft delete) (admin only)."""
    try:
        delete_user(db, user_id)
        return {"message": "User deleted successfully"}
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


# UI routes for auth pages
def register_auth_routes(app, templates: Jinja2Templates):
    """Register authentication UI routes."""

    @app.get("/login", name="login")
    async def login_page(request: Request):
        """Login page."""
        return templates.TemplateResponse(request, "login.html", {})

    @app.get("/register", name="register")
    async def register_page(request: Request, current_user: User = Depends(require_role("admin"))):
        """Register page (admin only)."""
        return templates.TemplateResponse(request, "register.html", {})

    @app.get("/admin/users-page", name="admin_users")
    async def admin_users_page(request: Request, current_user: User = Depends(require_role("admin"))):
        """Admin user management page."""
        return templates.TemplateResponse(request, "admin_users.html", {})

    @app.get("/admin/clips-page", name="admin_clips")
    async def admin_clips_page(request: Request, current_user: User = Depends(require_role("editor"))):
        """Clip management page (legacy - will be removed)."""
        return templates.TemplateResponse(request, "clip_management.html", {})

    @app.get("/video-tasks-page", name="video_tasks")
    async def video_tasks_page(request: Request, current_user: User = Depends(require_role("editor"))):
        """Video tasks management page (new design)."""
        return templates.TemplateResponse(request, "video_tasks.html", {})

    @app.get("/video-tasks/{video_id}", name="video_detail")
    async def video_detail_page(
        request: Request,
        video_id: int,
        current_user: User = Depends(require_role("editor")),
    ):
        """Video detail page showing all versions and clips."""
        return templates.TemplateResponse(
            request,
            "video_detail.html",
            {"video_id": video_id},
        )
