import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime
from database.models import Trade, Position, Base
from database.db_manager import DBManager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, delete
from brokers.base_broker import BaseBroker
from order_manager.manager import OrderManager  # Import the new OrderManager class

class MockBroker(BaseBroker):
    async def connect(self):
        pass

    async def get_cost_basis(self, symbol):
        return 1500.0

    async def get_positions(self):
        return ['AAPL', 'GOOGL']

    async def get_current_price(self, symbol):
        return 150.0

    async def execute_trade(self, *args):
        pass

    async def _get_account_info(self):
        return {'profile': {'account': {'account_number': '12345', 'value': 10000.0}}}

    async def _place_option_order(self, symbol, quantity, side, price=None):
        return {'status': 'filled', 'filled_price': 150.0}

    async def _place_future_option_order(self, symbol, quantity, side, price=None):
        return {'status': 'filled', 'filled_price': 150.0}

    async def _place_order(self, symbol, quantity, side, price=None):
        return {'status': 'filled', 'filled_price': 150.0}

    async def _get_order_status(self, order_id):
        return {'status': 'completed'}

    async def _cancel_order(self, order_id):
        return {'status': 'cancelled'}

    async def _get_options_chain(self, symbol, expiration_date):
        return {'options': 'chain'}


@pytest_asyncio.fixture(scope="module")
async def engine():
    engine = create_async_engine('sqlite+aiosqlite:///./test.db')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    Session = sessionmaker(bind=engine, class_=AsyncSession)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def truncate_tables(engine):
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(delete(table))
        await conn.commit()


@pytest_asyncio.fixture
async def broker(engine):
    return MockBroker(api_key="dummy_api_key", secret_key="dummy_secret_key", broker_name="dummy_broker", engine=engine)


@pytest_asyncio.fixture
async def order_manager(engine, broker):
    brokers = {"dummy_broker": broker}
    return OrderManager(engine, brokers)


@pytest.mark.asyncio
async def test_update_positions_buy(session, order_manager):
    trade = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, side="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
    async with session.begin():
        session.add(trade)
    await session.commit()
    await session.refresh(trade)

    await order_manager.update_positions(trade.id, session)

    result = await session.execute(select(Position).filter_by(symbol="AAPL"))
    position = result.scalars().first()
    assert position is not None
    assert position.symbol == "AAPL"
    assert position.quantity == 10
    assert position.latest_price == 150.0
    assert position.cost_basis == 1500.0


@pytest.mark.asyncio
async def test_update_positions_sell(session, order_manager):
    position = Position(symbol="AAPL", broker="dummy_broker", quantity=10, latest_price=150.0, cost_basis=1500.0)
    async with session.begin():
        session.add(position)
    await session.commit()

    trade = Trade(symbol="AAPL", quantity=5, price=155.0, executed_price=155.0, side="sell", timestamp=datetime.now(), status='filled', broker='dummy_broker')
    async with session.begin():
        session.add(trade)
    await session.commit()
    await session.refresh(trade)

    await order_manager.update_positions(trade, session)

    result = await session.execute(select(Position).filter_by(symbol="AAPL"))
    position = result.scalars().first()
    assert position.quantity == 5
    assert position.latest_price == 155.0
    assert position.cost_basis == 750.0


@pytest.mark.asyncio
async def test_full_sell_removes_position(session, order_manager):
    trade1 = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, side="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
    async with session.begin():
        session.add(trade1)
    await session.commit()
    await session.refresh(trade1)

    await order_manager.update_positions(trade1, session)

    trade2 = Trade(symbol="AAPL", quantity=10, price=155.0, executed_price=155.0, side="sell", timestamp=datetime.now(), status='filled', broker='dummy_broker')
    async with session.begin():
        session.add(trade2)
    await session.commit()
    await session.refresh(trade2)

    await order_manager.update_positions(trade2, session)

    result = await session.execute(select(Position).filter_by(symbol="AAPL"))
    assert result.scalar() is None


@pytest.mark.asyncio
async def test_multiple_buys_update_cost_basis(session, order_manager):
    trade1 = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, side="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
    async with session.begin():
        session.add(trade1)
    await session.commit()
    await session.refresh(trade1)

    await order_manager.update_positions(trade1, session)

    result = await session.execute(select(Position).filter_by(symbol="AAPL"))
    position = result.scalars().first()
    assert position.symbol == "AAPL"
    assert position.quantity == 10
    assert position.latest_price == 150.0
    assert position.cost_basis == 1500.0

    trade2 = Trade(symbol="AAPL", quantity=5, price=160.0, executed_price=160.0, side="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
    async with session.begin():
        session.add(trade2)
    await session.commit()
    await session.refresh(trade2)

    await order_manager.update_positions(trade2, session)

    result = await session.execute(select(Position).filter_by(symbol="AAPL"))
    position = result.scalars().first()
    assert position.quantity == 15
    assert position.latest_price == 160.0
    assert position.cost_basis == 2300.0
