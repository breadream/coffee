from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URI = "sqlite:///./cache.db"

# In FastAPI, more than one thread can interact with the database for the same request
engine = create_engine(
    SQLALCHEMY_DATABASE_URI, connect_args={"check_same_thread": False}
)

# each instance of the SessionLocal class becomes a db session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# parent class for the ORM models
Base = declarative_base()
