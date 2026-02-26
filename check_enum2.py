from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv(".env.production")
engine = create_engine(os.getenv("DATABASE_URL"))
with engine.connect() as conn:
    rows = conn.execute(
        text(
            "SELECT typname, enumlabel FROM pg_type t JOIN pg_enum e ON t.oid=e.enumtypid WHERE t.typname IN ('estadoseguimiento','valoracionriesgo') ORDER BY t.typname,e.enumsortorder; "
        )
    ).fetchall()
    print("enum tipo:", rows)
    samples = conn.execute(
        text("SELECT estado,valoracion_riesgo FROM seguimientos LIMIT 5; ")
    ).fetchall()
    print("sample rows:", samples)
engine.dispose()
