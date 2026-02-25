"""
seed_db.py  –  Run init_db.sql against the DATABASE_URL.
Railway doesn't mount SQL files like Docker, so we run this on first deploy.

Usage:  python seed_db.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Railway provides DATABASE_URL starting with "postgresql://"
# Some drivers need "postgresql://" not "postgres://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

engine = create_engine(DATABASE_URL)

sql_path = Path(__file__).resolve().parent / "init_db.sql"
sql = sql_path.read_text()

print("🔧 Running init_db.sql against the database...")
with engine.begin() as conn:
    # Execute each statement separately (split on semicolons)
    for statement in sql.split(";"):
        stmt = statement.strip()
        if stmt:
            conn.execute(text(stmt))

print("✅ Database seeded successfully!")
