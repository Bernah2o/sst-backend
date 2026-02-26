from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv(".env.production")
engine = create_engine(os.getenv("DATABASE_URL"))
with engine.connect() as conn:
    print(
        "enum types present:",
        conn.execute(
            text("SELECT typname FROM pg_type WHERE typname LIKE 'medicalaptitude%';")
        ).fetchall(),
    )
    print(
        "sample values",
        conn.execute(
            text("SELECT medical_aptitude_concept FROM occupational_exams LIMIT 5")
        ).fetchall(),
    )
engine.dispose()
