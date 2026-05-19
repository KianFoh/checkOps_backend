from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session as DBSession

from app.database import SessionLocal
from app.helpers.auth import build_activation_link
from app.helpers.auth import build_password_reset_link
from app.helpers.auth import create_email_verification_challenge
from app.helpers.auth import create_password_reset_challenge
from app.helpers.auth import create_token
from app.helpers.auth import get_latest_active_otp
from app.helpers.auth import get_latest_active_reset_otp
from app.helpers.auth import get_latest_active_reset_token
from app.helpers.auth import get_latest_active_token
from app.helpers.auth import hash_password
from app.helpers.auth import is_record_active
from app.helpers.auth import validate_activation_artifacts
from app.helpers.auth import validate_activation_token_only
from app.helpers.auth import validate_reset_artifacts
from app.helpers.auth import validate_reset_token_only
from app.helpers.auth import verify_password
from app.schemas.auth import EmailRequest
from app.schemas.auth import LinkValidationResponse
from app.schemas.auth import LoginRequest
from app.schemas.auth import LoginResponse
from app.schemas.auth import MessageResponse
from app.schemas.auth import ResetPasswordRequest
from app.schemas.auth import SetPasswordRequest
from app.schemas.auth import UserSummary
from app.schemas.auth import ValidateLinkRequest
from app.models.session import Session
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])

ACCESS_TOKEN_TTL_MINUTES = 15
REFRESH_TOKEN_TTL_DAYS = 7


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/email/activate", response_class=HTMLResponse, include_in_schema=False)
def open_activation_link(
    email: str,
    otp: str,
    token: str,
):
    deep_link = build_activation_link(email=email, otp=otp, token=token)
    return HTMLResponse(
        content=(
            "<!DOCTYPE html>"
            "<html><head><meta charset='utf-8'><title>Open App</title>"
            f"<meta http-equiv='refresh' content='0;url={deep_link}'>"
            "</head><body>"
            "<p>Opening Smart Checklist app...</p>"
            f"<p>If nothing happens, <a href='{deep_link}'>tap here</a>.</p>"
            "</body></html>"
        )
    )


@router.get("/password/open-reset", response_class=HTMLResponse, include_in_schema=False)
def open_password_reset_link(
    email: str,
    otp: str,
    token: str,
):
    deep_link = build_password_reset_link(email=email, otp=otp, token=token)
    return HTMLResponse(
        content=(
            "<!DOCTYPE html>"
            "<html><head><meta charset='utf-8'><title>Open App</title>"
            f"<meta http-equiv='refresh' content='0;url={deep_link}'>"
            "</head><body>"
            "<p>Opening Smart Checklist app...</p>"
            f"<p>If nothing happens, <a href='{deep_link}'>tap here</a>.</p>"
            "</body></html>"
        )
    )


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: DBSession = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email is not verified.",
        )

    now = datetime.utcnow()
    access_expires_at = now + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES)
    refresh_expires_at = now + timedelta(days=REFRESH_TOKEN_TTL_DAYS)

    db_session = Session(
        user_id=user.id,
        access_token=create_token(),
        refresh_token=create_token(),
        expires_at=refresh_expires_at,
        ip_address=request.client.host if request.client else None,
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    return LoginResponse(
        access_token=db_session.access_token,
        refresh_token=db_session.refresh_token,
        token_type="bearer",
        access_token_expires_at=access_expires_at,
        refresh_token_expires_at=refresh_expires_at,
        user=UserSummary(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            is_email_verified=user.is_email_verified,
        ),
    )


@router.post("/email/resend-activation", response_model=MessageResponse)
def resend_email_activation(
    payload: EmailRequest,
    db: DBSession = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified.",
        )

    active_otp = get_latest_active_otp(user.id, db)
    active_token = get_latest_active_token(user.id, db)
    if is_record_active(active_otp) or is_record_active(active_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current activation email is still active.",
        )

    create_email_verification_challenge(user=user, db=db)

    return MessageResponse(message="A new activation email has been sent.")


@router.post("/validate-link", response_model=LinkValidationResponse)
def validate_link(
    payload: ValidateLinkRequest,
    db: DBSession = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if payload.type == "activation":
        if user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already verified.",
            )

        token_record = validate_activation_token_only(user=user, token=payload.token, db=db)
        return LinkValidationResponse(
            message="Activation link is valid.",
            email=user.email,
            flow_type="activation",
            expires_at=token_record.expires_at,
        )

    if payload.type == "password_reset":
        if not user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is not active.",
            )

        token_record = validate_reset_token_only(user=user, token=payload.token, db=db)
        return LinkValidationResponse(
            message="Password reset link is valid.",
            email=user.email,
            flow_type="password_reset",
            expires_at=token_record.expires_at,
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid validation type.",
    )


@router.post("/email/set-password", response_model=MessageResponse)
def set_password_from_activation(
    payload: SetPasswordRequest,
    db: DBSession = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already activated.",
        )

    otp_record, token_record = validate_activation_artifacts(
        user=user,
        otp=payload.otp,
        token=payload.token,
        db=db,
    )

    user.password = hash_password(payload.password)
    user.is_email_verified = True
    otp_record.consumed_at = datetime.utcnow()
    token_record.consumed_at = datetime.utcnow()
    db.commit()

    return MessageResponse(message="Password set successfully. Account is now active.")


@router.post("/password/request-reset", response_model=MessageResponse)
def request_password_reset(
    payload: EmailRequest,
    db: DBSession = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is not active.",
        )

    create_password_reset_challenge(user=user, db=db)

    return MessageResponse(message="Password reset email has been sent.")


@router.post("/password/resend-reset", response_model=MessageResponse)
def resend_password_reset(
    payload: EmailRequest,
    db: DBSession = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is not active.",
        )

    active_otp = get_latest_active_reset_otp(user.id, db)
    active_token = get_latest_active_reset_token(user.id, db)
    if is_record_active(active_otp) or is_record_active(active_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password reset email is still active.",
        )

    create_password_reset_challenge(user=user, db=db)

    return MessageResponse(message="A new password reset email has been sent.")


@router.post("/password/reset", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    db: DBSession = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is not active.",
        )

    otp_record, token_record = validate_reset_artifacts(
        user=user,
        otp=payload.otp,
        token=payload.token,
        db=db,
    )

    user.password = hash_password(payload.password)
    otp_record.consumed_at = datetime.utcnow()
    token_record.consumed_at = datetime.utcnow()
    db.commit()

    return MessageResponse(message="Password reset successfully.")
