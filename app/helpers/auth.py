import os
from datetime import datetime, timedelta
import hashlib
import hmac
import secrets
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

from fastapi import HTTPException, status
from dotenv import load_dotenv
from sqlalchemy.orm import Session as DBSession

from app.models.email_verification_otp import EmailVerificationOTP
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_otp import PasswordResetOTP
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User

load_dotenv()


def clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip().strip("\"").strip("'")
    return cleaned or None


def clean_smtp_password(value: str | None) -> str | None:
    cleaned = clean_env_value(value)
    if cleaned is None:
        return None

    # Gmail app passwords are often copied with spaces for readability.
    return cleaned.replace(" ", "")

OTP_TTL_MINUTES = 10
VERIFICATION_TOKEN_TTL_MINUTES = 10
RESET_OTP_TTL_MINUTES = 10
RESET_TOKEN_TTL_MINUTES = 10
PBKDF2_ITERATIONS = 100_000
EMAIL_FROM = clean_env_value(os.getenv("EMAIL_FROM")) or "noreply@example.com"
SMTP_HOST = clean_env_value(os.getenv("SMTP_HOST"))
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = clean_env_value(os.getenv("SMTP_USERNAME"))
SMTP_PASSWORD = clean_smtp_password(os.getenv("SMTP_PASSWORD"))
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
API_HOSTNAME = (clean_env_value(os.getenv("API_HOSTNAME")) or "http://127.0.0.1:8000").rstrip("/")
APP_DEEP_LINK_BASE = os.getenv(
    "ACTIVATION_DEEP_LINK_BASE",
    "smartchecklist://activate-account",
)
PASSWORD_RESET_DEEP_LINK_BASE = os.getenv(
    "PASSWORD_RESET_DEEP_LINK_BASE",
    "smartchecklist://reset-password",
)


def create_token() -> str:
    return secrets.token_urlsafe(48)


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(raw_password: str, stored_password: str) -> bool:
    if not stored_password:
        return False

    if stored_password.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, expected_hash = stored_password.split("$", 3)
        except ValueError:
            return False

        computed_hash = hashlib.pbkdf2_hmac(
            "sha256",
            raw_password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return hmac.compare_digest(computed_hash, expected_hash)

    return hmac.compare_digest(raw_password, stored_password)


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def get_latest_active_otp(user_id: int, db: DBSession) -> EmailVerificationOTP | None:
    return (
        db.query(EmailVerificationOTP)
        .filter(
            EmailVerificationOTP.user_id == user_id,
            EmailVerificationOTP.consumed_at.is_(None),
        )
        .order_by(EmailVerificationOTP.created_at.desc())
        .first()
    )


def get_latest_active_token(user_id: int, db: DBSession) -> EmailVerificationToken | None:
    return (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.consumed_at.is_(None),
        )
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )


def get_latest_active_reset_otp(user_id: int, db: DBSession) -> PasswordResetOTP | None:
    return (
        db.query(PasswordResetOTP)
        .filter(
            PasswordResetOTP.user_id == user_id,
            PasswordResetOTP.consumed_at.is_(None),
        )
        .order_by(PasswordResetOTP.created_at.desc())
        .first()
    )


def get_latest_active_reset_token(user_id: int, db: DBSession) -> PasswordResetToken | None:
    return (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.consumed_at.is_(None),
        )
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )


def is_record_active(record) -> bool:
    return record is not None and record.expires_at >= datetime.utcnow()


def build_activation_link(email: str, otp: str, token: str) -> str:
    return f"{APP_DEEP_LINK_BASE}?{urlencode({'email': email, 'otp': otp, 'token': token})}"


def build_password_reset_link(email: str, otp: str, token: str) -> str:
    return f"{PASSWORD_RESET_DEEP_LINK_BASE}?{urlencode({'email': email, 'otp': otp, 'token': token})}"


def build_activation_bridge_link(email: str, otp: str, token: str) -> str:
    return f"{API_HOSTNAME}/auth/email/activate?{urlencode({'email': email, 'otp': otp, 'token': token})}"


def build_password_reset_bridge_link(email: str, otp: str, token: str) -> str:
    return f"{API_HOSTNAME}/auth/password/open-reset?{urlencode({'email': email, 'otp': otp, 'token': token})}"


def can_send_email() -> bool:
    return all([SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM])


def send_email(subject: str, recipient: str, body: str, html_body: str | None = None) -> None:
    if not can_send_email():
        print("[EMAIL PLACEHOLDER] SMTP config incomplete")
        print(f"From: {EMAIL_FROM}")
        print(f"To: {recipient}")
        print(f"Subject: {subject}")
        print(body)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = EMAIL_FROM
    message["To"] = recipient
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.ehlo()
        if SMTP_USE_TLS:
            smtp.starttls()
            smtp.ehlo()
        try:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
        except smtplib.SMTPAuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="SMTP authentication failed. Check SMTP_USERNAME and SMTP_PASSWORD in .env.",
            ) from exc
        except smtplib.SMTPException as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email via SMTP.",
            ) from exc


def send_verification_email(email: str, otp: str, token: str) -> None:
    activation_link = build_activation_bridge_link(email=email, otp=otp, token=token)
    body = (
        "Use the OTP below to activate your Smart Checklist account.\n\n"
        f"OTP: {otp}\n\n"
        "Please open this email on your mobile device. "
        "The activation link only works from the Smart Checklist mobile app.\n\n"
        f"Activate account: {activation_link}\n\n"
        "This activation request expires in 10 minutes."
    )
    html_body = (
        "<p>Use the OTP below to activate your Smart Checklist account.</p>"
        f"<p><strong>OTP: {otp}</strong></p>"
        "<p>Please open this email on your mobile device. "
        "The activation link only works from the Smart Checklist mobile app.</p>"
        f'<p><a href="{activation_link}">Activate account</a></p>'
        "<p>This activation request expires in 10 minutes.</p>"
    )
    send_email("Activate your Smart Checklist account", email, body, html_body)


def send_password_reset_email(email: str, otp: str, token: str) -> None:
    reset_link = build_password_reset_bridge_link(email=email, otp=otp, token=token)
    body = (
        "Use the OTP below to reset your Smart Checklist password.\n\n"
        f"OTP: {otp}\n\n"
        "Please open this email on your mobile device. "
        "The reset link only works from the Smart Checklist mobile app.\n\n"
        f"Reset password: {reset_link}\n\n"
        "This password reset request expires in 10 minutes."
    )
    html_body = (
        "<p>Use the OTP below to reset your Smart Checklist password.</p>"
        f"<p><strong>OTP: {otp}</strong></p>"
        "<p>Please open this email on your mobile device. "
        "The reset link only works from the Smart Checklist mobile app.</p>"
        f'<p><a href="{reset_link}">Reset password</a></p>'
        "<p>This password reset request expires in 10 minutes.</p>"
    )
    send_email("Reset your Smart Checklist password", email, body, html_body)


def create_email_verification_challenge(
    user: User,
    db: DBSession,
) -> None:
    otp = generate_otp()
    token = create_token()
    now = datetime.utcnow()

    db.query(EmailVerificationOTP).filter(
        EmailVerificationOTP.user_id == user.id,
        EmailVerificationOTP.consumed_at.is_(None),
    ).delete(synchronize_session=False)
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.consumed_at.is_(None),
    ).delete(synchronize_session=False)

    db.add(
        EmailVerificationOTP(
            user_id=user.id,
            otp_hash=hash_secret(otp),
            expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
        )
    )
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_secret(token),
            expires_at=now + timedelta(minutes=VERIFICATION_TOKEN_TTL_MINUTES),
        )
    )
    db.commit()

    send_verification_email(email=user.email, otp=otp, token=token)


def create_password_reset_challenge(
    user: User,
    db: DBSession,
) -> None:
    otp = generate_otp()
    token = create_token()
    now = datetime.utcnow()

    db.query(PasswordResetOTP).filter(
        PasswordResetOTP.user_id == user.id,
        PasswordResetOTP.consumed_at.is_(None),
    ).delete(synchronize_session=False)
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.consumed_at.is_(None),
    ).delete(synchronize_session=False)

    db.add(
        PasswordResetOTP(
            user_id=user.id,
            otp_hash=hash_secret(otp),
            expires_at=now + timedelta(minutes=RESET_OTP_TTL_MINUTES),
        )
    )
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_secret(token),
            expires_at=now + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
        )
    )
    db.commit()

    send_password_reset_email(email=user.email, otp=otp, token=token)


def validate_activation_artifacts(
    user: User,
    otp: str,
    token: str,
    db: DBSession,
) -> tuple[EmailVerificationOTP, EmailVerificationToken]:
    otp_record = get_latest_active_otp(user.id, db)
    token_record = get_latest_active_token(user.id, db)

    if otp_record is None or token_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active activation request found.",
        )

    now = datetime.utcnow()
    if otp_record.expires_at < now or token_record.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activation link has expired.",
        )

    if not hmac.compare_digest(otp_record.otp_hash, hash_secret(otp)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP.",
        )

    if not hmac.compare_digest(token_record.token_hash, hash_secret(token)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid activation token.",
        )

    return otp_record, token_record


def validate_activation_token_only(
    user: User,
    token: str,
    db: DBSession,
) -> EmailVerificationToken:
    token_record = get_latest_active_token(user.id, db)
    if token_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active activation request found.",
        )

    if token_record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activation link has expired.",
        )

    if not hmac.compare_digest(token_record.token_hash, hash_secret(token)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid activation token.",
        )

    return token_record


def validate_reset_artifacts(
    user: User,
    otp: str,
    token: str,
    db: DBSession,
) -> tuple[PasswordResetOTP, PasswordResetToken]:
    otp_record = get_latest_active_reset_otp(user.id, db)
    token_record = get_latest_active_reset_token(user.id, db)

    if otp_record is None or token_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active password reset request found.",
        )

    now = datetime.utcnow()
    if otp_record.expires_at < now or token_record.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset link has expired.",
        )

    if not hmac.compare_digest(otp_record.otp_hash, hash_secret(otp)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP.",
        )

    if not hmac.compare_digest(token_record.token_hash, hash_secret(token)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token.",
        )

    return otp_record, token_record


def validate_reset_token_only(
    user: User,
    token: str,
    db: DBSession,
) -> PasswordResetToken:
    token_record = get_latest_active_reset_token(user.id, db)
    if token_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active password reset request found.",
        )

    if token_record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset link has expired.",
        )

    if not hmac.compare_digest(token_record.token_hash, hash_secret(token)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token.",
        )

    return token_record
