from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class Strategy(Base):
    __tablename__ = 'strategies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    # Define relationships
    trades = relationship('Trade', back_populates='strategy')
    balances = relationship('Balance', back_populates='strategy')
    positions = relationship('Position', back_populates='strategy')

    def can_trade(self, symbol):
        # Implement your logic to determine if the strategy can trade the given symbol
        return True

class Trade(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    executed_price = Column(Float, nullable=True)
    order_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    broker = Column(String, nullable=False)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False)
    profit_loss = Column(Float, nullable=True)
    success = Column(String, nullable=True)
    balance_id = Column(Integer, ForeignKey('balances.id'))

    strategy = relationship('Strategy', back_populates='trades')
    balance = relationship('Balance', back_populates='trades')

class AccountInfo(Base):
    __tablename__ = 'account_info'
    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String, unique=True)
    value = Column(Float)

class Balance(Base):
    __tablename__ = 'balances'
    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String)
    strategy_id = Column(Integer, ForeignKey('strategies.id'))
    initial_balance = Column(Float, default=0.0)
    total_balance = Column(Float, default=0.0)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    trades = relationship('Trade', back_populates='balance')
    positions = relationship('Position', back_populates='balance')

    strategy = relationship('Strategy', back_populates='balances')

class Position(Base):
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    balance_id = Column(Integer, ForeignKey('balances.id'), nullable=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False)
    broker = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    latest_price = Column(Float, nullable=False)
    cost = Column(Float, nullable=True)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)

    balance = relationship('Balance', back_populates='positions')
    strategy = relationship('Strategy', back_populates='positions')

def drop_then_init_db(engine):
    Base.metadata.drop_all(engine)  # Drop all tables
    Base.metadata.create_all(engine)  # Create new tables

def init_db(engine):
    Base.metadata.create_all(engine)  # Create new tables
