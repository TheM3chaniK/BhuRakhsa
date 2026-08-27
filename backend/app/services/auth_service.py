from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    """Service providing core user registration, authentication, token rotation, and revocation."""

    @staticmethod
    async def register_user(db: AsyncSession, register_data: RegisterRequest) -> User:
        """Register a new civilian user account."""
        normalized_email = register_data.email.strip().lower()

        # Check existing user
        query = select(User).where(User.email == normalized_email)
        result = await db.execute(query)
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        # Hash password and ensure civilian role
        hashed_pwd = hash_password(register_data.password)
        new_user = User(
            full_name=register_data.full_name.strip(),
            email=normalized_email,
            phone=register_data.phone.strip() if register_data.phone else None,
            password_hash=hashed_pwd,
            role=UserRole.CIVILIAN,  # Explicitly always CIVILIAN for public registration
            is_active=True,
            is_verified=False,
        )

        db.add(new_user)
        try:
            await db.commit()
            await db.refresh(new_user)
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        return new_user

    @staticmethod
    async def authenticate_user(db: AsyncSession, login_data: LoginRequest) -> User:
        """Authenticate user credentials and update last login timestamp."""
        normalized_email = login_data.email.strip().lower()

        query = select(User).where(User.email == normalized_email)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user or not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Update last login time
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)

        return user

    @staticmethod
    async def create_tokens_for_user(db: AsyncSession, user: User) -> TokenResponse:
        """Create a new access token and a hashed persistent refresh token for a user."""
        access_token = create_access_token(subject=user.id)
        raw_refresh_token = generate_refresh_token()
        token_hash_val = hash_refresh_token(raw_refresh_token)

        refresh_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash_val,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(refresh_record)
        await db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @classmethod
    async def rotate_refresh_token(
        cls, db: AsyncSession, raw_refresh_token: str
    ) -> TokenResponse:
        """Validate and rotate an existing refresh token, issuing a new pair and revoking the old one."""
        token_hash_val = hash_refresh_token(raw_refresh_token)

        query = (
            select(RefreshToken)
            .options(selectinload(RefreshToken.user))
            .where(RefreshToken.token_hash == token_hash_val)
        )
        result = await db.execute(query)
        token_record = result.scalar_one_or_none()

        if not token_record or token_record.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked refresh token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if token_record.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not token_record.user or not token_record.user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive or not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Revoke the current refresh token
        token_record.revoked_at = datetime.now(timezone.utc)

        # Issue new token pair
        return await cls.create_tokens_for_user(db, token_record.user)

    @staticmethod
    async def revoke_refresh_token(db: AsyncSession, raw_refresh_token: str) -> None:
        """Revoke a refresh token on user logout."""
        token_hash_val = hash_refresh_token(raw_refresh_token)

        query = select(RefreshToken).where(RefreshToken.token_hash == token_hash_val)
        result = await db.execute(query)
        token_record = result.scalar_one_or_none()

        if token_record and token_record.revoked_at is None:
            token_record.revoked_at = datetime.now(timezone.utc)
            await db.commit()
