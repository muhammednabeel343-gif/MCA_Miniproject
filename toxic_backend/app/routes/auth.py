import re
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    require_active_user
)
from app.services.moderation import refresh_moderation_status

router = APIRouter(prefix="/auth", tags=["auth"])

# Email regex pattern
EMAIL_PATTERN = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")


class UserRegister(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username_or_email: str
    password: str


@router.post("/register")
def register(data: UserRegister, db: Session = Depends(get_db)):
    username = data.username.strip()
    email = data.email.strip().lower()
    password = data.password

    # Validate inputs
    if not username or not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All fields are required"
        )

    if len(username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters long"
        )

    if not EMAIL_PATTERN.match(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )

    if len(password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 4 characters long"
        )

    # Validate unique username
    existing_username = db.query(User).filter(User.username == username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Validate unique email
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    hashed = hash_password(password)
    new_user = User(
        username=username,
        email=email,
        password_hash=hashed,
        role="USER",
        account_status="ACTIVE",
        warning_count=0
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": new_user.id,
        "username": new_user.username,
        "email": new_user.email,
        "role": new_user.role,
        "account_status": new_user.account_status,
        "message": "User registered successfully"
    }


@router.post("/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    req_input = data.username_or_email.strip()
    password = data.password

    # Find user by username or email
    user = db.query(User).filter(
        (User.username == req_input) | (User.email == req_input.lower())
    ).first()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username/email or password"
        )

    refresh_moderation_status(user, db)

    # Generate token (sub: username)
    token = create_access_token({"sub": user.username})
    return {
        "token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "account_status": user.account_status
        }
    }


@router.get("/me")
def get_me(user: User = Depends(require_active_user)):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "account_status": user.account_status,
        "warning_count": user.warning_count
    }
