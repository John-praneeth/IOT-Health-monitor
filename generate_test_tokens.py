"""Generate backend-compatible JWT tokens for WebSocket auth testing.

Outputs:
VALID_TOKEN   -> expires in ~1 hour
EXPIRED_TOKEN -> already expired
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import os

from dotenv import load_dotenv
from jose import jwt


# Load backend environment so we use the same SECRET_KEY as the API.
backend_env = Path(__file__).resolve().parent / "backend" / ".env"
load_dotenv(dotenv_path=backend_env)


# Match backend auth settings from backend/auth.py
SECRET_KEY = os.getenv("SECRET_KEY", "iot-healthcare-super-secret-key-change-in-production")
ALGORITHM = "HS256"


# Claims that match backend expectations (backend reads `sub`).
BASE_PAYLOAD = {
    "sub": "test_user",
    "user_id": "test_user",
    "role": "ADMIN",
}


def build_token(expires_delta: timedelta) -> str:
    payload = BASE_PAYLOAD.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def main() -> None:
    valid_token = build_token(timedelta(hours=1))
    expired_token = build_token(timedelta(hours=-1))

    print(f'VALID_TOKEN = "{valid_token}"')
    print(f'EXPIRED_TOKEN = "{expired_token}"')


if __name__ == "__main__":
    main()
