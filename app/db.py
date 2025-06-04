# db.py
import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("Falta definir DATABASE_URL en .env")

engine = create_engine(DATABASE_URL, future=True)
