from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv('.env.production')
engine = create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    print('lesson status enum', conn.execute(text("SELECT enumlabel FROM pg_type t JOIN pg_enum e ON t.oid=e.enumtypid WHERE t.typname='lessonstatus';")).fetchall())
    print('sample rows', conn.execute(text("SELECT status FROM interactive_lessons LIMIT 5")).fetchall())
engine.dispose()