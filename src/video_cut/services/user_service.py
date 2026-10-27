"""User management service with CRUD operations."""

from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from video_cut.db.models import User
from video_cut.auth.auth import hash_password, verify_password


class UserServiceError(Exception):
    """Base exception for user service operations."""

    pass


class UserNotFoundError(UserServiceError):
    """Raised when a user is not found."""

    pass


class UserAlreadyExistsError(UserServiceError):
    """Raised when trying to create a user that already exists."""

    pass


class InvalidCredentialsError(UserServiceError):
    """Raised when credentials are invalid."""

    pass


def create_user(
    db: Session,
    username: str,
    email: str,
    password: str,
    role: str = "editor",
) -> User:
    """Create a new user.

    Args:
        db: Database session
        username: Unique username
        email: Unique email address
        password: Plain text password (will be hashed)
        role: User role (admin, editor, viewer)

    Returns:
        Created User object

    Raises:
        UserAlreadyExistsError: If username or email already exists
    """
    # Check if username or email already exists
    existing = db.query(User).filter(
        or_(User.username == username, User.email == email)
    ).first()

    if existing:
        if existing.username == username:
            raise UserAlreadyExistsError(f"Username '{username}' already exists")
        else:
            raise UserAlreadyExistsError(f"Email '{email}' already exists")

    # Validate role
    valid_roles = ["admin", "editor", "viewer"]
    if role not in valid_roles:
        raise UserServiceError(f"Invalid role: {role}. Must be one of {valid_roles}")

    # Create new user
    hashed_password = hash_password(password)
    user = User(
        username=username,
        email=email,
        password_hash=hashed_password,
        role=role,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get a user by ID.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        User object or None if not found
    """
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get a user by username.

    Args:
        db: Database session
        username: Username

    Returns:
        User object or None if not found
    """
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get a user by email.

    Args:
        db: Database session
        email: Email address

    Returns:
        User object or None if not found
    """
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, username: str, password: str) -> User:
    """Authenticate a user with username and password.

    Args:
        db: Database session
        username: Username
        password: Plain text password

    Returns:
        Authenticated User object

    Raises:
        InvalidCredentialsError: If credentials are invalid
    """
    user = get_user_by_username(db, username)

    if user is None:
        raise InvalidCredentialsError("Invalid username or password")

    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid username or password")

    if not user.is_active:
        raise InvalidCredentialsError("User account is inactive")

    return user


def update_user(
    db: Session,
    user_id: int,
    username: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> User:
    """Update user information.

    Args:
        db: Database session
        user_id: User ID to update
        username: New username (optional)
        email: New email (optional)
        password: New password (optional, will be hashed)
        role: New role (optional)
        is_active: New active status (optional)

    Returns:
        Updated User object

    Raises:
        UserNotFoundError: If user not found
        UserAlreadyExistsError: If new username or email conflicts
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        raise UserNotFoundError(f"User with ID {user_id} not found")

    # Update username if provided
    if username and username != user.username:
        existing = get_user_by_username(db, username)
        if existing:
            raise UserAlreadyExistsError(f"Username '{username}' already exists")
        user.username = username

    # Update email if provided
    if email and email != user.email:
        existing = get_user_by_email(db, email)
        if existing:
            raise UserAlreadyExistsError(f"Email '{email}' already exists")
        user.email = email

    # Update password if provided
    if password:
        user.password_hash = hash_password(password)

    # Update role if provided
    if role:
        valid_roles = ["admin", "editor", "viewer"]
        if role not in valid_roles:
            raise UserServiceError(f"Invalid role: {role}")
        user.role = role

    # Update active status if provided
    if is_active is not None:
        user.is_active = is_active

    db.commit()
    db.refresh(user)

    return user


def delete_user(db: Session, user_id: int) -> bool:
    """Delete a user (soft delete by setting is_active=False).

    Args:
        db: Database session
        user_id: User ID to delete

    Returns:
        True if user was deleted

    Raises:
        UserNotFoundError: If user not found
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        raise UserNotFoundError(f"User with ID {user_id} not found")

    user.is_active = False
    db.commit()

    return True


def list_users(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> list[User]:
    """List users with optional filters.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        role: Filter by role (optional)
        is_active: Filter by active status (optional)

    Returns:
        List of User objects
    """
    query = db.query(User)

    if role:
        query = query.filter(User.role == role)

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    return query.offset(skip).limit(limit).all()


def count_users(db: Session, is_active: Optional[bool] = None) -> int:
    """Count total number of users.

    Args:
        db: Database session
        is_active: Filter by active status (optional)

    Returns:
        Count of users
    """
    query = db.query(User)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    return query.count()
