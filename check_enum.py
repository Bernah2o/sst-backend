from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv(".env.production")
url = os.getenv("DATABASE_URL")
print("DATABASE_URL", url)
engine = create_engine(url)
with engine.connect() as conn:
    print(
        "table exists",
        conn.execute(text("SELECT to_regclass('public.seguimientos');")).fetchone(),
    )
    print(
        "enum exists",
        conn.execute(
            text(
                "SELECT exists(SELECT 1 FROM pg_type WHERE typname='estadoseguimiento_enum');"
            )
        ).fetchone(),
    )
engine.dispose()
