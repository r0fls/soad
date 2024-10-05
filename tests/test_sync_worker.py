from datetime import datetime, timezone

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from data.sync_worker import PositionService, BalanceService, BrokerService, _get_async_engine, _run_sync_worker_iteration
from database.models import Position, Balance

# Mock data for testing
MOCK_POSITIONS = [
    Position(symbol='AAPL', broker='tradier', latest_price=0, last_updated=datetime.now(), underlying_volatility=None),
    Position(symbol='GOOG', broker='tastytrade', latest_price=0, last_updated=datetime.now(), underlying_volatility=None),
]

MOCK_BALANCE = Balance(broker='tradier', strategy='RSI', type='cash', balance=10000.0, timestamp=datetime.now())


@pytest.mark.asyncio
async def test_update_position_prices_and_volatility():
    # Mock the broker service
    mock_broker_service = AsyncMock()
    mock_broker_service.get_latest_price = AsyncMock(return_value=150.0)  # Ensure it's async

    # Initialize PositionService with the mocked broker service
    position_service = PositionService(mock_broker_service)

    # Mock session and positions
    mock_session = AsyncMock(spec=AsyncSession)  # Ensure we are using AsyncSession
    mock_positions = MOCK_POSITIONS

    # Test the method
    timestamp = datetime.now(timezone.utc)
    await position_service.update_position_prices_and_volatility(mock_session, mock_positions, timestamp)

    # Assert that the broker service was called to get the latest price for each position
    mock_broker_service.get_latest_price.assert_any_call('tradier', 'AAPL')
    mock_broker_service.get_latest_price.assert_any_call('tastytrade', 'GOOG')

    # Assert that the session commit was called
    assert mock_session.commit.called

@pytest.fixture
def broker_service():
    brokers = {
        'mock_broker': MagicMock()
    }
    return BrokerService(brokers)


@pytest.fixture
def position_service(broker_service):
    return PositionService(broker_service)


@pytest.fixture
def balance_service(broker_service):
    return BalanceService(broker_service)


@pytest.mark.asyncio
async def test_get_broker_instance(broker_service):
    broker_instance = broker_service.get_broker_instance('mock_broker')
    assert broker_instance == broker_service.brokers['mock_broker']


@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_get_latest_price_async(mock_logger, broker_service):
    mock_broker = AsyncMock()
    mock_broker.get_current_price = AsyncMock(return_value=100)
    broker_service.brokers['mock_broker'] = mock_broker
    price = await broker_service.get_latest_price('mock_broker', 'AAPL')
    assert price == 100
    mock_broker.get_current_price.assert_awaited_once_with('AAPL')


@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_update_position_price(mock_logger, position_service):
    mock_session = AsyncMock(AsyncSession)
    mock_position = Position(symbol='AAPL', broker='mock_broker', quantity=10)
    # Mocking external dependencies
    position_service.broker_service.get_latest_price = AsyncMock(return_value=150)
    position_service._get_underlying_symbol = MagicMock(return_value='AAPL')
    position_service._calculate_historical_volatility = AsyncMock(return_value=0.2)
    await position_service._update_position_price(mock_session, mock_position, datetime.now())
    assert mock_position.latest_price == 150
    assert mock_position.underlying_volatility == 0.2
    assert mock_session.commit.called


@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_update_strategy_balance(mock_logger, balance_service):
    mock_session = AsyncMock(AsyncSession)
    mock_session.execute.side_effect = [
        AsyncMock(scalar=MagicMock(return_value=None)),  # Cash balance query
        AsyncMock(scalar=MagicMock(return_value=None))   # Positions balance query
    ]
    await balance_service.update_strategy_balance(mock_session, 'mock_broker', 'strategy1', datetime.now())
    assert mock_session.add.called  # Check that session.add was called to add a new balance record
    assert mock_session.commit.called

@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_update_uncategorized_balances(mock_logger, balance_service):
    mock_session = AsyncMock(AsyncSession)
    balance_service.broker_service.get_account_info = AsyncMock(return_value={'value': 1000})
    balance_service._sum_all_strategy_balances = AsyncMock(return_value=800)
    await balance_service.update_uncategorized_balances(mock_session, 'mock_broker', datetime.now())
    assert mock_session.add.called  # Check that a new balance record was added
    assert mock_session.commit.called  # Ensure the session was committed

@pytest.mark.asyncio
async def test_get_positions(position_service):
    mock_session = AsyncMock(AsyncSession)
    mock_broker_positions = {'AAPL': 'mock_position'}
    # Mock the dependencies of position_service instead of position_service itself
    position_service.broker_service.get_broker_instance = MagicMock()
    position_service.broker_service.get_broker_instance.return_value.get_positions.return_value = mock_broker_positions
    position_service._fetch_db_positions = AsyncMock(return_value={})
    broker_positions, db_positions = await position_service._get_positions(mock_session, 'mock_broker')
    assert broker_positions == mock_broker_positions
    assert db_positions == {}

@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_fetch_and_log_price(mock_logger, position_service):
    mock_position = Position(symbol='AAPL', broker='mock_broker')
    position_service.broker_service.get_latest_price = AsyncMock(return_value=150)
    price = await position_service._fetch_and_log_price(mock_position)
    assert price == 150
    mock_logger.debug.assert_called_with('Updated latest price for AAPL to 150')


def test_strip_timezone(position_service):
    timestamp_with_tz = datetime.now(timezone.utc)
    timestamp_naive = position_service._strip_timezone(timestamp_with_tz)
    assert timestamp_naive.tzinfo is None

def test_fetch_broker_instance(broker_service):
    broker_instance = broker_service._fetch_broker_instance('mock_broker')
    assert broker_instance == broker_service.brokers['mock_broker']


@pytest.mark.asyncio
async def test_fetch_price(broker_service):
    mock_broker = AsyncMock()
    mock_broker.get_current_price = AsyncMock(return_value=100)
    price = await broker_service._fetch_price(mock_broker, 'AAPL')
    assert price == 100

@pytest.mark.asyncio
async def test_insert_new_position():
    # Mock the session and broker position
    mock_session = AsyncMock(spec=AsyncSession)
    mock_broker_position = {
        'symbol': 'AAPL',
        'quantity': 10,
        'latest_price': 150.0
    }
    # Create PositionService and timestamp
    position_service = PositionService(AsyncMock())
    now = datetime.now()

    # Call the method
    await position_service._insert_new_position(mock_session, 'mock_broker', mock_broker_position, now)

    # Verify session.add was called with the correct new position
    mock_session.add.assert_called_once()
    added_position = mock_session.add.call_args[0][0]
    assert added_position.broker == 'mock_broker'
    assert added_position.strategy == 'uncategorized'
    assert added_position.symbol == 'AAPL'
    assert added_position.quantity == 10
    assert added_position.latest_price == 150.0
    assert added_position.last_updated == now

    # Verify that commit was called
    mock_session.commit.assert_awaited_once()

@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_insert_or_update_balance(mock_logger, balance_service):
    mock_session = AsyncMock(AsyncSession)
    await balance_service._insert_or_update_balance(mock_session, 'mock_broker', 'strategy1', 1000, datetime.now())
    assert mock_session.add.called  # Ensure a new balance record was added
    assert mock_session.commit.called  # Ensure the session was committed


@pytest.mark.asyncio
async def test_get_async_engine():
    engine_url = "sqlite+aiosqlite:///:memory:"
    async_engine = await _get_async_engine(engine_url)
    assert async_engine.name == "sqlite"
