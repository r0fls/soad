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
#import logging
#logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
class MockBroker(BaseBroker):
    async def connect(self):
        pass

    async def get_positions(self):
        return ['AAPL', 'GOOGL']

    async def get_current_price(self, symbol):
        return 150.0

    async def execute_trade(self, *args):
        pass

    async def _get_account_info(self):
        return {'profile': {'account': {'account_number': '12345', 'value': 10000.0}}}

    async def _place_option_order(self, symbol, quantity, order_type, price=None):
        return {'status': 'filled', 'filled_price': 150.0}

    async def _place_future_option_order(self, symbol, quantity, order_type, price=None):
        return {'status': 'filled', 'filled_price': 150.0}

    async def _place_order(self, symbol, quantity, order_type, price=None):
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
            # Correct delete statement for each table
            await conn.execute(delete(table))
        await conn.commit()  # Make sure to commit the transaction after deletion


@pytest_asyncio.fixture
async def broker(engine):
    return MockBroker(api_key="dummy_api_key", secret_key="dummy_secret_key", broker_name="dummy_broker", engine=engine)


@pytest.mark.asyncio
async def test_has_bought_today(session, broker):
    async with session.begin():
        trade = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        session.add(trade)
    await session.commit()
    await session.refresh(trade)

    result = await broker.has_bought_today("AAPL")
    assert result is True

    await session.execute(delete(Trade).filter_by(symbol="AAPL"))
    await session.commit()
    result = await broker.has_bought_today("AAPL")
    assert result is False


@pytest.mark.asyncio
async def test_update_positions_buy(session, broker):
    trade = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
    async with session.begin():
        session.add(trade)
    await session.commit()
    await session.refresh(trade)

    await broker.update_positions(trade)

    result = await session.execute(select(Position).filter_by(symbol="AAPL"))
    position = result.scalars().first()
    assert position is not None
    assert position.symbol == "AAPL"
    assert position.quantity == 10
    assert position.latest_price == 150.0
    assert position.cost_basis == 1500.0


@pytest.mark.asyncio
async def test_update_positions_sell(session, broker):
    position = Position(symbol="AAPL", broker="dummy_broker", quantity=10, latest_price=150.0, cost_basis=1500.0)
    async with session.begin():
        session.add(position)
    await session.commit()

    trade = Trade(symbol="AAPL", quantity=5, price=155.0, executed_price=155.0, order_type="sell", timestamp=datetime.now(), status='filled', broker='dummy_broker')
    async with session.begin():
        session.add(trade)
    await session.commit()
    await session.refresh(trade)

    await broker.update_positions(trade)

    result = await session.execute(select(Position).filter_by(symbol="AAPL"))
    position = result.scalars().first()
    assert position.quantity == 5
    assert position.latest_price == 155.0
    assert position.cost_basis == 750.0

@pytest.mark.asyncio
async def test_multiple_buys_update_cost_basis(session, broker):
    # First buy trade
    trade1 = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')

    session.add(trade1)
    await session.commit()  # Commit the first transaction
    await session.refresh(trade1)

    # Update the position after the first trade
    await broker.update_positions(trade1)

    # Verify the position after the first trade
    result = await session.execute(select(Position).filter_by(symbol="AAPL"))
    position = result.scalars().first()
    assert position.symbol == "AAPL"
    assert position.quantity == 10
    assert position.latest_price == 150.0
    assert position.cost_basis == 1500.0

    # Second buy trade
    trade2 = Trade(symbol="AAPL", quantity=5, price=160.0, executed_price=160.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')

    session.add(trade2)
    await session.commit()  # Commit the second transaction
    await session.refresh(trade2)

    # Update the position after the second trade
    await broker.update_positions(trade2)

    # Verify the position after the second trade
    result = await session.execute(select(Position).filter_by(symbol="AAPL"))
    position = result.scalars().first()

    # Verify updated position and cost basis
    assert position.quantity == 15
    assert position.latest_price == 160.0
    assert position.cost_basis == 2300.0

@pytest.mark.asyncio
async def test_full_sell_removes_position(session, broker):
    trade1 = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
    session.add(trade1)
    await session.commit()
    await session.refresh(trade1)

    await broker.update_positions(trade1)

    trade2 = Trade(symbol="AAPL", quantity=10, price=155.0, executed_price=155.0, order_type="sell", timestamp=datetime.now(), status='filled', broker='dummy_broker')
    session.add(trade2)
    await session.commit()
    await session.refresh(trade2)

    await broker.update_positions(trade2)

    position = await session.execute(select(Position).filter_by(symbol="AAPL"))

    assert position.scalar() is None



@pytest.mark.asyncio
async def test_edge_case_zero_quantity(session, broker):
    trade = Trade(symbol="AAPL", quantity=0, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
    async with session.begin():
        session.add(trade)
    await session.commit()
    await session.refresh(trade)

    await broker.update_positions(trade)

    result = await session.execute(select(Position).filter_by(symbol="AAPL"))
    position = result.scalars().first()
    assert position is None


@pytest.mark.asyncio
async def test_pl_calculation_buy_trade(session, broker):
    trade = Trade(
        symbol="AAPL",
        quantity=10,
        price=150.0,
        executed_price=150.0,
        order_type="buy",
        status="executed",
        timestamp=datetime.now(),
        broker="dummy_broker",
        strategy="test_strategy",
        profit_loss=None,
        success="yes"
    )
    async with session.begin():
        session.add(trade)
    await session.commit()
    await session.refresh(trade)

    profit_loss = await broker.db_manager.calculate_profit_loss(trade)
    assert profit_loss is None


@pytest.mark.asyncio
async def test_pl_calculation_option_full_sell_trade(session, broker):
    position = Position(
        symbol="QQQ240726P00470000",
        broker="dummy_broker",
        quantity=10,
        latest_price=150.0,
        cost_basis=1500.0,
        last_updated=datetime.now(),
        strategy="test_strategy"
    )
    async with session.begin():
        session.add(position)
    await session.commit()

    trade = Trade(
        symbol="QQQ240726P00470000",
        quantity=10,
        price=155.0,
        executed_price=155.0,
        order_type="sell",
        status="executed",
        timestamp=datetime.now(),
        broker="dummy_broker",
        strategy="test_strategy",
        profit_loss=None,
        success="yes"
    )
    async with session.begin():
        session.add(trade)
    await session.commit()
    await session.refresh(trade)

    profit_loss = await broker.db_manager.calculate_profit_loss(trade)
    assert profit_loss == 5000.0


@pytest.mark.asyncio
async def test_pl_calculation_full_sell_trade(session, broker):
    position = Position(
        symbol="AAPL",
        broker="dummy_broker",
        quantity=10,
        latest_price=150.0,
        cost_basis=1500.0,
        last_updated=datetime.now(),
        strategy="test_strategy"
    )
    async with session.begin():
        session.add(position)
    await session.commit()

    trade = Trade(
        symbol="AAPL",
        quantity=10,
        price=155.0,
        executed_price=155.0,
        order_type="sell",
        status="executed",
        timestamp=datetime.now(),
        broker="dummy_broker",
        strategy="test_strategy",
        profit_loss=None,
        success="yes"
    )
    async with session.begin():
        session.add(trade)
    await session.commit()
    await session.refresh(trade)

    profit_loss = await broker.db_manager.calculate_profit_loss(trade)
    assert profit_loss == 50.0


@pytest.mark.asyncio
async def test_pl_calculation_sell_trade(session, broker):
    position = Position(
        symbol="AAPL",
        broker="dummy_broker",
        quantity=10,
        latest_price=150.0,
        cost_basis=1500.0,
        last_updated=datetime.now(),
        strategy="test_strategy"
    )
    async with session.begin():
        session.add(position)
    await session.commit()

    trade = Trade(
        symbol="AAPL",
        quantity=5,
        price=155.0,
        executed_price=155.0,
        order_type="sell",
        status="executed",
        timestamp=datetime.now(),
        broker="dummy_broker",
        strategy="test_strategy",
        profit_loss=None,
        success="yes"
    )
    async with session.begin():
        session.add(trade)
    await session.commit()
    await session.refresh(trade)

    profit_loss = await broker.db_manager.calculate_profit_loss(trade)
    assert profit_loss == 25.0


@pytest.mark.asyncio
async def test_pl_calculation_no_position(session, broker):
    trade = Trade(
        symbol="AAPL",
        quantity=5,
        price=155.0,
        executed_price=155.0,
        order_type="sell",
        status="executed",
        timestamp=datetime.now(),
        broker="dummy_broker",
        strategy="test_strategy",
        profit_loss=None,
        success="yes"
    )
    async with session.begin():
        session.add(trade)
    await session.commit()
    await session.refresh(trade)

    profit_loss = await broker.db_manager.calculate_profit_loss(trade)
    assert profit_loss is None
