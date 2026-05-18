# alembic/env.py

import os
import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

# Alembic Config object
config = context.config

# Load .env from project root
# Project structure:
# Smart-Checklist-Management-System/
# ├── .env
# ├── alembic/
# │   └── env.py
# └── app/
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Read database settings from .env
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

# Validate required variables
missing = [
    name for name, value in {
        "DB_USER": DB_USER,
        "DB_PASSWORD": DB_PASSWORD,
        "DB_NAME": DB_NAME,
    }.items()
    if not value
]

if missing:
    raise ValueError(
        f"Missing required environment variables in .env: {', '.join(missing)}"
    )

# Build SQLAlchemy URL from .env values
DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Override sqlalchemy.url from alembic.ini
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Ensure project root is importable
sys.path.append(str(BASE_DIR))

# Import Base and all models so Alembic can detect them
from app.database import Base
from app.models.email_verification_otp import EmailVerificationOTP  # noqa
from app.models.email_verification_token import EmailVerificationToken  # noqa
from app.models.password_reset_otp import PasswordResetOTP  # noqa
from app.models.password_reset_token import PasswordResetToken  # noqa
from app.models.user import User  # noqa
from app.models.task import Task  # noqa
from app.models.session import Session  # noqa

target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
