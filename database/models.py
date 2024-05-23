from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Trade(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String)
    quantity = Column(Integer)
    price = Column(Float)
    order_type = Column(String)
    status = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    brokerage = Column(String)
    strategy = Column(String)

class AccountInfo(Base):
    __tablename__ = 'account_info'
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(JSON)

DATABASE_URL = "sqlite:///trades.db"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)
