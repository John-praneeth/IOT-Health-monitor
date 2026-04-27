"""Generate backend-compatible JWT tokens for WebSocket auth testing.

Outputs:
VALID_TOKEN   -> expires in ~1 hour
EXPIRED_TOKEN -> already expired
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import uuid

from dotenv import load_dotenv
from jose import jwt


# Load backend environment so we use the same SECRET_KEY as the API.
backend_env = Path(__file__).resolve().parent / "backend" / ".env"
load_dotenv(dotenv_path=backend_env)


# Match backend auth settings from backend/auth.py
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in backend/.env before generating tokens.")
ALGORITHM = "HS256"


# Claims that match backend expectations (backend reads `sub` and token type).
DEFAULT_SUBJECT = os.getenv("TOKEN_SUB", "admin")
DEFAULT_ROLE = os.getenv("TOKEN_ROLE", "ADMIN")


def build_token(expires_delta: timedelta, *, subject: str = DEFAULT_SUBJECT, role: str = DEFAULT_ROLE) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid.uuid4().hex,
        "typ": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def main() -> None:
    valid_token = build_token(timedelta(hours=1))
    expired_token = build_token(timedelta(hours=-1))

    print(f'VALID_TOKEN = "{valid_token}"')
    print(f'EXPIRED_TOKEN = "{expired_token}"')
    print(f'SUBJECT = "{DEFAULT_SUBJECT}"')


if __name__ == "__main__":
    main()
