from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, PrimaryKeyConstraint, Index
from datetime import datetime

Base = declarative_base()

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
    strategy = Column(String, nullable=True)
    profit_loss = Column(Float, nullable=True)
    success = Column(String, nullable=True)

class AccountInfo(Base):
    __tablename__ = 'account_info'
    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String, unique=True)
    value = Column(Float)

class Balance(Base):
    __tablename__ = 'balances'
    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String, nullable=False)
    strategy = Column(String, nullable=True)
    type = Column(String, nullable=False)  # 'cash' or 'positions'
    balance = Column(Float, default=0.0)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    positions = relationship("Position", back_populates="balance", foreign_keys="[Position.balance_id]", primaryjoin="and_(Balance.id==Position.balance_id, Balance.type=='positions')")

    __table_args__ = (
        PrimaryKeyConstraint('id', name='balance_pk'),
        Index('ix_broker_strategy_timestamp', 'broker', 'strategy', 'timestamp'),
        Index('ix_type_timestamp', 'type', 'timestamp'),
    )

class Position(Base):
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String, nullable=False)
    strategy = Column(String, nullable=True)
    balance_id = Column(Integer, ForeignKey('balances.id'), nullable=True)
    symbol = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    latest_price = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=False)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)
    underlying_volatility = Column(Float, nullable=True)
    underlying_latest_price = Column(Float, nullable=True)

    balance = relationship("Balance", back_populates="positions", foreign_keys=[balance_id])

# Async engine setup
DATABASE_URL = "postgresql+asyncpg://user:password@localhost/dbname"
engine = create_async_engine(DATABASE_URL, echo=True)

# Async session setup
async_session = sessionmaker(
    engine, expire_on_commit=True, class_=AsyncSession
)

# Drop and create tables asynchronously
async def drop_then_init_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

async def init_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
