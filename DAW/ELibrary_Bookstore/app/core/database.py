import os
from sqlalchemy import create_engine
# Am înlocuit declarative_base cu DeclarativeBase
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/ELibrary_Bookstore_db"

engine = create_engine(DATABASE_URL, echo=True) 

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ==========================================
# REZOLVAREA EROARII PYLANCE
# Acum Base este o clasă reală, nu o variabilă
# ==========================================
class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()