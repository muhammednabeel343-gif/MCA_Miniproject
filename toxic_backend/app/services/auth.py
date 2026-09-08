import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Query
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import User
from backend.app.services.moderation import refresh_moderation_status

# Load secret key from environment
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_for_gaming_platform_toxicity_detection")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24

# API Key header helper for routing protection
API_KEY_HEADER = APIKeyHeader(name="Authorization", auto_error=False)


# -----------------------------
# Password Hashing Utility
# -----------------------------
def hash_password(password: str) -> str:
    """Hash password using PBKDF2-SHA256."""
    salt = secrets.token_bytes(16)
    iterations = 100000
    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_b64 = base64.b64encode(salt).decode("utf-8")
    hash_b64 = base64.b64encode(hash_bytes).decode("utf-8")
    return f"pbkdf2_sha256${iterations}${salt_b64}${hash_b64}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify standard PBKDF2-SHA256 password hashes."""
    try:
        if not hashed_password or "$" not in hashed_password:
            return False
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2])
        original_hash = base64.b64decode(parts[3])
        new_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return secrets.compare_digest(original_hash, new_hash)
    except Exception:
        return False


# -----------------------------
# Custom JWT Hashing Utilities
# -----------------------------
def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def base64url_decode(data: str) -> bytes:
    padding = "=" * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT-compatible HS256 signed access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    
    # Store timestamp in UTC seconds
    to_encode.update({"exp": int(expire.timestamp())})
    
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    
    header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_json = json.dumps(to_encode, separators=(",", ":")).encode("utf-8")
    
    header_b64 = base64url_encode(header_json)
    payload_b64 = base64url_encode(payload_json)
    
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify access token, verifying expiration."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        
        header_b64, payload_b64, signature_b64 = parts
        
        # Verify Signature
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
        expected_signature_b64 = base64url_encode(expected_signature)
        
        if not secrets.compare_digest(signature_b64, expected_signature_b64):
            return None
        
        # Parse payload
        payload_bytes = base64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
        
        # Check Expiration
        exp = payload.get("exp")
        if exp is None:
            return None
        if datetime.utcnow().timestamp() > exp:
            return None
            
        return payload
    except Exception:
        return None


# -----------------------------
# Protected Endpoint Dependencies
# -----------------------------
def get_current_user(
    auth_header: Optional[str] = Depends(API_KEY_HEADER),
    db: Session = Depends(get_db)
) -> User:
    """Dependency to retrieve currently authenticated user from Bearer Token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not auth_header:
        raise credentials_exception
        
    try:
        # Expect "Bearer <token>"
        parts = auth_header.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise credentials_exception
        token = parts[1]
    except Exception:
        raise credentials_exception
        
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
        
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
        
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    refresh_moderation_status(user, db)
    return user


def require_active_user(user: User = Depends(get_current_user)) -> User:
    """Require authentication while allowing blocked users to access profiles."""
    return user


def require_game_access(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Allow active and restricted users, but reject blocked users."""
    refresh_moderation_status(user, db)
    if user.account_status == "BLOCKED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Blocked users cannot create rooms, join rooms, or play games",
        )
    return user


def require_admin(user: User = Depends(require_active_user)) -> User:
    """Ensure user has admin privileges."""
    if user.account_status == "BLOCKED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Blocked users cannot perform administrative actions",
        )
    if user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required to perform this action"
        )
    return user
