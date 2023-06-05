from sqlalchemy import create_engine, Column, String
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URI = "sqlite:///./vin_records.db"

# In FastAPI, more than one thread can interact with the database for the same request
engine = create_engine(
    SQLALCHEMY_DATABASE_URI, connect_args={"check_same_thread": False}
)

# each instance of the SessionLocal class becomes a db session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# parent class for the ORM models
Base = declarative_base()


class VinRecord(Base):
    __tablename__ = "vin_records"

    vin = Column(String(17), primary_key=True, index=True)
    make = Column(String)
    model = Column(String)
    model_year = Column(String)
    body_class = Column(String)


Base.metadata.create_all(bind=engine)


def get_db():
    """
    Dependency function to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
