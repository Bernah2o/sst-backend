import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv('.env.production')
engine=create_engine(os.getenv('DATABASE_URL'))
Session=sessionmaker(bind=engine)
from app.models.interactive_lesson import InteractiveLesson
s=Session()
print('lesson', s.query(InteractiveLesson).limit(1).all())
s.close()