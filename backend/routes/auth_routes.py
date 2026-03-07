"""
AUTH ROUTES
NarrativeIQ — /api/auth/* endpoints
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.auth_models import (
    UserDB, RegisterRequest, LoginRequest,
    TokenResponse, UserResponse
)
from auth_utils import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# ─────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user.
    Returns a JWT token immediately so the user is logged in after signup.
    """
    # Check email not already taken
    existing = db.query(UserDB).filter(UserDB.email == body.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    # Create user
    user = UserDB(
        name=body.name.strip(),
        email=body.email.lower().strip(),
        password_hash=hash_password(body.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        email=user.email
    )


# ─────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with email + password.
    Returns a JWT token on success.
    """
    user = db.query(UserDB).filter(UserDB.email == body.email.lower()).first()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated."
        )

    token = create_access_token(user.id, user.email)

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        email=user.email
    )


# ─────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────

@router.post("/logout")
def logout(current_user: UserDB = Depends(get_current_user)):
    """
    Logout endpoint.
    JWTs are stateless — the client must delete the token.
    This endpoint confirms the token is valid before the client clears it.
    """
    return {"status": "logged out", "user_id": current_user.id}


# ─────────────────────────────────────────
# GET CURRENT USER
# ─────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def get_me(current_user: UserDB = Depends(get_current_user)):
    """
    Returns the currently authenticated user's profile.
    Protected — requires Authorization: Bearer <token> header.
    """
    return current_user
