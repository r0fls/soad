from datetime import datetime, timezone

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock, ANY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from data.sync_worker import PositionService, BalanceService, BrokerService, _get_async_engine, _run_sync_worker_iteration, _fetch_and_update_positions, _reconcile_brokers_and_update_balances
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
    mock_broker_instance = AsyncMock()
    mock_broker_instance.get_latest_price = AsyncMock(return_value=150.0)
    mock_broker_instance.get_cost_basis = MagicMock(return_value=100.0)  # Synchronous function

    # Mock get_broker_instance to return the mock broker instance
    mock_broker_service.get_broker_instance = AsyncMock(return_value=mock_broker_instance)

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

    mock_broker_instance.get_cost_basis.assert_any_call('AAPL')
    mock_broker_instance.get_cost_basis.assert_any_call('GOOG')

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
    broker_instance = await broker_service.get_broker_instance('mock_broker')
    assert broker_instance == broker_service.brokers['mock_broker']


@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_get_latest_price_async(mock_logger, broker_service):
    mock_broker = MagicMock()
    mock_broker.get_current_price = AsyncMock(return_value=100)
    broker_service.get_broker_instance = AsyncMock(return_value=mock_broker)
    price = await broker_service.get_latest_price('mock_broker', 'AAPL')
    assert price == 100
    mock_broker.get_current_price.assert_awaited_once_with('AAPL')

@pytest.mark.skip
@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_update_strategy_balance(mock_logger, balance_service):
    mock_session = AsyncMock(AsyncSession)
    mock_session.execute.side_effect = [
        AsyncMock(scalar=MagicMock(return_value=None)),  # Cash balance query
        MagicMock(scalar=MagicMock(return_value=None))   # Positions balance query
    ]
    await balance_service.update_strategy_balance(mock_session, 'mock_broker', 'strategy1', datetime.now())
    assert mock_session.add.called  # Check that session.add was called to add a new balance record
    assert mock_session.commit.called

@pytest.mark.skip
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

    position_service.broker_service.get_broker_instance = AsyncMock()
    mock_broker_instance = MagicMock()
    mock_broker_instance.get_positions.return_value = mock_broker_positions
    position_service.broker_service.get_broker_instance.return_value = mock_broker_instance

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

@pytest.mark.asyncio
async def test_fetch_broker_instance(broker_service):
    broker_instance = await broker_service._fetch_broker_instance('mock_broker')
    assert broker_instance == broker_service.brokers['mock_broker']


@pytest.mark.asyncio
async def test_fetch_price(broker_service):
    mock_broker = AsyncMock()
    mock_broker.get_current_price = AsyncMock(return_value=100)
    price = await broker_service._fetch_price(mock_broker, 'AAPL')
    assert price == 100

@pytest.mark.skip
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

@pytest.mark.skip
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

@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_fetch_and_update_positions(mock_logger):
    mock_session = AsyncMock()
    mock_position_service = AsyncMock()
    mock_positions = AsyncMock()

    # Mock session.execute to return mock positions
    mock_session.execute.return_value = mock_positions

    await _fetch_and_update_positions(mock_session, mock_position_service, datetime.now())

    mock_session.execute.assert_called_once_with(ANY)
    #mock_position_service.update_position_prices_and_volatility.assert_awaited_once_with(mock_session, mock_positions.scalars(), ANY)
    mock_logger.info.assert_any_call('Positions fetched')

@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_reconcile_brokers_and_update_balances(mock_logger):
    mock_session = AsyncMock()
    mock_position_service = AsyncMock()
    mock_balance_service = AsyncMock()
    mock_brokers = ['broker1', 'broker2']
    mock_now = datetime.now()  # Capture datetime once

    await _reconcile_brokers_and_update_balances(mock_session, mock_position_service, mock_balance_service, mock_brokers, mock_now)

    # Ensure reconcile positions and update balances are called for both brokers
    mock_position_service.reconcile_positions.assert_any_await(mock_session, 'broker1')
    mock_position_service.reconcile_positions.assert_any_await(mock_session, 'broker2')
    mock_balance_service.update_all_strategy_balances.assert_any_await(mock_session, 'broker1', mock_now)
    mock_balance_service.update_all_strategy_balances.assert_any_await(mock_session, 'broker2', mock_now)

# TODO: Fix this test or refactor
@pytest.mark.skip
@pytest.mark.asyncio
async def test_update_strategy_and_uncategorized_balances():
    # Mock broker_service
    mock_broker_service = MagicMock()
    mock_broker_service.get_account_info.return_value = {'value': 30000}
    mock_broker_service.get_latest_price.side_effect = lambda broker, symbol: 100 if symbol == 'AAPL' else 200 if symbol == 'GOOGL' else 150

    # Create the BalanceService instance
    balance_service = BalanceService(mock_broker_service)
    balance_service._get_strategies = AsyncMock(return_value=['test_strategy'])

    # Mock SQLAlchemy session
    mock_session = AsyncMock(spec=AsyncSession)

    # Mock the strategy cash and position balances
    mock_cash_balance = Balance(broker='tradier', strategy='test_strategy', type='cash', balance=5000, timestamp=datetime.now())
    mock_position_balance = Balance(broker='tradier', strategy='test_strategy', type='positions', balance=10000, timestamp=datetime.now())

    mock_session.execute.side_effect = [
        MagicMock(scalar=MagicMock(return_value=None)),  # Cash balance query
        MagicMock(scalar=MagicMock(return_value=None))   # Positions balance query
    ]

    # Mock query results for cash and positions balance
    mock_session.execute.return_value.scalars.side_effect = [
        [mock_cash_balance],  # First call returns cash balance
        [mock_position_balance],  # Second call returns position balance
        []  # Assume no further results
    ]

    # Mock current positions for the strategy
    mock_position = Position(broker='tradier', strategy='test_strategy', symbol='AAPL', quantity=50, latest_price=100, last_updated=datetime.now())
    mock_session.execute.return_value.scalars.return_value = [mock_position]

    # Mock the strategy and uncategorized balance update process
    await balance_service.update_all_strategy_balances(mock_session, 'tradier', datetime.now())

    # Check that the balances were inserted/updated correctly
    mock_session.add.assert_any_call(Balance(
        broker='tradier',
        strategy='test_strategy',
        type='cash',
        balance=5000,
        timestamp=ANY
    ))

    mock_session.add.assert_any_call(Balance(
        broker='tradier',
        strategy='test_strategy',
        type='positions',
        balance=10000,
        timestamp=pytest.any
    ))

    # Check uncategorized balance calculation
    uncategorized_balance = 30000 - (5000 + 10000)
    mock_session.add.assert_any_call(Balance(
        broker='tradier',
        strategy='uncategorized',
        type='cash',
        balance=uncategorized_balance,
        timestamp=pytest.any
    ))

    # Ensure the session commits were called
    assert mock_session.commit.call_count == 3

@pytest.mark.skip
@pytest.mark.asyncio
async def test_insert_or_update_position():
    # Mock the session and broker position
    mock_session = AsyncMock(spec=AsyncSession)
    mock_broker_position_existing = {
        'symbol': 'AAPL',
        'quantity': 15,
        'latest_price': 150.0,
        'last_updated': datetime.now()
    }
    mock_broker_position_new = {
        'symbol': 'MSFT',
        'quantity': 20,
        'latest_price': 200.0
    }

    now = datetime.now()
    # Simulate an existing position in the DB
    existing_position = Position(
        broker='mock_broker',
        symbol='AAPL',
        quantity=10,
        latest_price=100.0,
        last_updated=now
    )

    # Mock the query for existing positions to return the existing AAPL position
    mock_session.execute.return_value.scalars.return_value = [existing_position]

    # Create PositionService and timestamp
    position_service = PositionService(AsyncMock())

    # Test updating the existing AAPL position
    await position_service._insert_new_position(mock_session, 'mock_broker', mock_broker_position_existing, now)

    # Check that the existing AAPL position was updated, not inserted
    assert existing_position.quantity == 10
    assert existing_position.latest_price == 100.0
    assert existing_position.last_updated == now

    # Test inserting a new MSFT position
    await position_service._insert_new_position(mock_session, 'mock_broker', mock_broker_position_new, now)

    # Verify that a new position was added for MSFT
    mock_session.add.assert_called()
    added_position = mock_session.add.call_args[0][0]
    assert added_position.broker == 'mock_broker'
    assert added_position.symbol == 'MSFT'
    assert added_position.quantity == 20
    assert added_position.latest_price == 200.0
    assert added_position.last_updated == now

    # Ensure session.commit() is called once after updating both positions
    assert mock_session.commit.await_count == 2

@pytest.mark.asyncio
async def test_remove_excess_uncategorized_positions_no_categorized():
    # Mock session
    mock_session = AsyncMock(spec=AsyncSession)

    # Mock broker and DB positions
    db_positions = {
        'AAPL': Position(symbol='AAPL', strategy='uncategorized', quantity=100),
    }
    broker_positions = {
        'AAPL': {'quantity': 80}
    }

    # Create PositionService instance
    position_service = PositionService(AsyncMock())

    # Call the function
    await position_service._remove_excess_uncategorized_positions(mock_session, 'mock_broker', db_positions, broker_positions)

    # Ensure the quantity is updated correctly
    assert db_positions['AAPL'].quantity == 80
    mock_session.add.assert_called_once_with(db_positions['AAPL'])

@pytest.mark.asyncio
async def test_remove_excess_uncategorized_positions_with_categorized():
    # Mock session
    mock_session = AsyncMock(spec=AsyncSession)

    # Mock broker and DB positions
    db_positions = {
        'AAPL': Position(symbol='AAPL', strategy='uncategorized', quantity=100),
        'AAPL_cat': Position(symbol='AAPL', strategy='categorized', quantity=20)
    }
    broker_positions = {
        'AAPL': {'quantity': 80}
    }

    # Create PositionService instance
    position_service = PositionService(AsyncMock())

    # Call the function
    await position_service._remove_excess_uncategorized_positions(mock_session, 'mock_broker', db_positions, broker_positions)

    # Ensure the quantity is updated correctly, accounting for categorized position (80 - 20 = 60)
    assert db_positions['AAPL'].quantity == 60
    mock_session.add.assert_called_once_with(db_positions['AAPL'])

@pytest.mark.asyncio
async def test_remove_excess_uncategorized_positions_no_change_needed():
    # Mock session
    mock_session = AsyncMock(spec=AsyncSession)

    # Mock broker and DB positions
    db_positions = {
        'AAPL': Position(symbol='AAPL', strategy='uncategorized', quantity=50),
        'AAPL_cat': Position(symbol='AAPL', strategy='categorized', quantity=20)
    }
    broker_positions = {
        'AAPL': {'quantity': 70}  # Broker position matches DB (50 uncategorized + 20 categorized)
    }

    # Create PositionService instance
    position_service = PositionService(AsyncMock())

    # Call the function
    await position_service._remove_excess_uncategorized_positions(mock_session, 'mock_broker', db_positions, broker_positions)

    # Ensure no updates were made
    mock_session.add.assert_not_called()

@pytest.mark.asyncio
async def test_remove_excess_uncategorized_positions_no_broker_position():
    # Mock session
    mock_session = AsyncMock(spec=AsyncSession)

    # Mock broker and DB positions
    db_positions = {
        'AAPL': Position(symbol='AAPL', strategy='uncategorized', quantity=100)
    }
    broker_positions = {}  # No broker position for AAPL

    # Create PositionService instance
    position_service = PositionService(AsyncMock())

    # Call the function
    await position_service._remove_excess_uncategorized_positions(mock_session, 'mock_broker', db_positions, broker_positions)

    # Ensure no updates were made since there's no broker position for AAPL
    mock_session.add.assert_not_called()

@pytest.mark.asyncio
async def test_remove_excess_uncategorized_positions_negative_net_broker_quantity():
    # Mock session
    mock_session = AsyncMock(spec=AsyncSession)

    # Mock broker and DB positions
    db_positions = {
        'AAPL': Position(symbol='AAPL', strategy='uncategorized', quantity=100),
        'AAPL_cat': Position(symbol='AAPL', strategy='categorized', quantity=90)
    }
    broker_positions = {
        'AAPL': {'quantity': 80}
    }

    # Create PositionService instance
    position_service = PositionService(AsyncMock())

    # Call the function
    await position_service._remove_excess_uncategorized_positions(mock_session, 'mock_broker', db_positions, broker_positions)

    # Since categorized quantity (90) exceeds broker quantity (80), uncategorized position should be set to 0
    assert db_positions['AAPL'].quantity == 0
    mock_session.add.assert_called_once_with(db_positions['AAPL'])


@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_run_sync_worker_iteration_timeout(mock_logger):
    # Mock services and session
    mock_session_factory = MagicMock()  # Mock the Session factory
    mock_session = AsyncMock()  # Mock the actual session object
    # Ensure the mock session works with 'async with'
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    # When the session is called, return the async mock session
    mock_session_factory.return_value = mock_session
    mock_position_service = AsyncMock()
    mock_balance_service = AsyncMock()
    mock_brokers = ['mock_broker']
    # Set a very short timeout for testing
    short_timeout = 0.01  # 10 milliseconds

    # Mock the functions to sleep for a while to trigger the timeout
    async def slow_reconcile(*args, **kwargs):
        await asyncio.sleep(0.02)  # 20 milliseconds to trigger timeout
    mock_position_service.reconcile_positions = AsyncMock(side_effect=slow_reconcile)
    mock_balance_service.update_all_strategy_balances = AsyncMock()

    # Call the sync worker iteration with the short timeout and assert it raises a TimeoutError
    with pytest.raises(asyncio.TimeoutError):
        await _run_sync_worker_iteration(mock_session_factory, mock_position_service, mock_balance_service, mock_brokers, short_timeout)

    # Ensure the logger captured the timeout
    mock_logger.error.assert_any_call('Iteration exceeded the maximum allowed time. Forcing restart.')

    # Ensure reconcile and update methods were attempted
    mock_position_service.reconcile_positions.assert_called_once_with(mock_session, 'mock_broker')
    mock_balance_service.update_all_strategy_balances.assert_not_called()  # Should not reach this due to timeout
