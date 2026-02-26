import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv(".env.production")
engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
from app.models.seguimiento import Seguimiento

sess = Session()
print("first seguimiento", sess.query(Seguimiento).limit(1).all())
sess.close()
