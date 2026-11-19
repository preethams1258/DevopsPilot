from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import User, AuditLog
from app.schemas.api import RegisterRequest, LoginRequest, TokenResponse
from app.core.security import hash_password, verify_password, create_token, get_current_user
import jwt
from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(409, "Email is already registered")
    role = "admin" if db.scalar(select(func.count(User.id))) == 0 else "engineer"
    user = User(email=payload.email.lower(), full_name=payload.full_name, password_hash=hash_password(payload.password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(AuditLog(user_id=user.id, action="register", resource_type="user", resource_id=str(user.id)))
    db.commit()
    return TokenResponse(access_token=create_token(user), refresh_token=create_token(user, "refresh"))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return TokenResponse(access_token=create_token(user), refresh_token=create_token(user, "refresh"))


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role}


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: dict, db: Session = Depends(get_db)):
    try:
        claims = jwt.decode(payload.get("refresh_token", ""), settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if claims.get("type") != "refresh":
            raise ValueError("Wrong token type")
        user = db.get(User, int(claims["sub"]))
        if not user or not user.is_active:
            raise ValueError("Inactive user")
    except Exception:
        raise HTTPException(401, "Invalid or expired refresh token") from None
    return TokenResponse(access_token=create_token(user), refresh_token=create_token(user, "refresh"))
