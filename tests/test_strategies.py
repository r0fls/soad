import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from strategies.base_strategy import BaseStrategy
from sqlalchemy import select
from database.models import Balance, Position
from sqlalchemy.ext.asyncio import AsyncSession


class TestBaseStrategy(BaseStrategy):
    def __init__(self, broker):
        super().__init__(broker, 'test_strategy', 10000)
        return

    async def rebalance(self):
        pass

@pytest.fixture
def broker():
    broker = MagicMock()

    # Mock get_account_info to return a dictionary with an integer buying_power
    broker.get_account_info = AsyncMock()
    broker.get_account_info.return_value = {'buying_power': 20000}

    # Mock Session and its return value
    session_mock = MagicMock()
    broker.Session.return_value.__enter__.return_value = session_mock

    # Mock query result for Balance
    balance_mock = MagicMock()
    balance_mock.balance = 10000
    session_mock.query.return_value.filter_by.return_value.first.return_value = balance_mock

    return broker

@pytest.fixture
def strategy(broker):
    return TestBaseStrategy(broker)


@pytest.mark.asyncio
async def test_initialize_starting_balance_existing(strategy):
    # Mock the async session
    mock_session = AsyncMock()
    strategy.broker.Session.return_value.__aenter__.return_value = mock_session

    # Create a mock balance object
    mock_balance = MagicMock()
    mock_balance.balance = 1000  # Set an example balance

    # Simulate session.execute() returning a mock result
    mock_result = MagicMock()
    mock_result.scalar.return_value = mock_balance
    mock_session.execute.return_value = mock_result

    # Call the initialize_starting_balance method
    await strategy.initialize_starting_balance()

    # Build the expected query
    expected_query = select(Balance).filter_by(
        strategy=strategy.strategy_name,
        broker=strategy.broker.broker_name,
        type='cash'
    ).order_by(Balance.timestamp.desc())

    # Verify that execute() was called with the correct query using SQL string comparison
    mock_session.execute.assert_called_once()

    # Compare the SQL representation
    actual_query = str(mock_session.execute.call_args[0][0])
    expected_query_str = str(expected_query)

    assert actual_query == expected_query_str, f"Expected query: {expected_query_str}, but got: {actual_query}"

    # Ensure that the balance was not re-added since it already exists
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_initialize_starting_balance_new(strategy):
    # Mock the async session
    mock_session = AsyncMock()
    strategy.broker.Session.return_value.__aenter__.return_value = mock_session

    # Simulate session.execute() returning a mock result
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_session.execute.return_value = mock_result

    # Call the initialize_starting_balance method
    await strategy.initialize_starting_balance()

    # Build the expected query
    expected_query = select(Balance).filter_by(
        strategy=strategy.strategy_name,
        broker=strategy.broker.broker_name,
        type='cash'
    ).order_by(Balance.timestamp.desc())

    # Verify that execute() was called with the correct query using SQL string comparison
    mock_session.execute.assert_called_once()

    # Compare the SQL representation
    actual_query = str(mock_session.execute.call_args[0][0])
    expected_query_str = str(expected_query)

    assert actual_query == expected_query_str, f"Expected query: {expected_query_str}, but got: {actual_query}"

    # Ensure that the balance was not re-added since it already exists
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
@patch('strategies.base_strategy.datetime')
@patch('strategies.base_strategy.asyncio.iscoroutinefunction')
@patch('strategies.base_strategy.BaseStrategy.should_own')
async def test_sync_positions_with_broker(mock_should_own, mock_iscoroutinefunction, mock_datetime, strategy):
    # Mock method return values
    mock_should_own.return_value = 5
    mock_datetime.utcnow.return_value = datetime(2023, 1, 1)
    strategy.broker.get_positions.return_value = {'AAPL': {'quantity': 10}}
    strategy.broker.get_current_price.return_value = 150
    # Mock strategy.get_db_positions to return an empty list
    strategy.get_db_positions = AsyncMock(return_value=[])
    mock_iscoroutinefunction.return_value = False

    # Create a mock Position object
    mock_position = MagicMock()
    mock_position.strategy = None
    mock_position.symbol = 'AAPL'
    # Mock the AsyncSession and session.execute() behavior
    session_mock = AsyncMock(spec=AsyncSession)
    # Mock the result of session.execute().scalar() to return the mock_position on the first call
    mock_result = MagicMock()

    # Setup the side_effect for scalar() to simulate returning the Position and None on subsequent calls
    mock_result.scalar.side_effect = [mock_position, None]

    # Mock the result of scalars().all() to return an empty list
    mock_result.scalars.return_value.all.return_value = []

    # Mock session.execute to return the mock result
    session_mock.execute.return_value = mock_result

    # Set strategy.broker.Session to return this mocked session
    strategy.broker.Session.return_value.__aenter__.return_value = session_mock

    # Call the sync_positions_with_broker method
    await strategy.sync_positions_with_broker()

    # Verify that session.add() and session.commit() are called correctly
    session_mock.add.assert_called_once()
    session_mock.commit.assert_called_once()

def test_calculate_target_balances(strategy):
    total_balance = 10000
    cash_percentage = 0.2
    target_cash_balance, target_investment_balance = strategy.calculate_target_balances(total_balance, cash_percentage)
    assert target_cash_balance == 2000
    assert target_investment_balance == 8000

@pytest.mark.asyncio
@patch('strategies.base_strategy.asyncio.iscoroutinefunction', return_value=False)
async def skip_test_fetch_current_db_positions(strategy):
    session_mock = strategy.broker.Session.return_value.__enter__.return_value
    session_mock.query.return_value.filter_by.return_value.all.return_value = [
        MagicMock(symbol='AAPL', quantity=10)
    ]
    positions = await strategy.fetch_current_db_positions()
    assert positions == {'AAPL': 10}

@pytest.mark.asyncio
@patch('strategies.base_strategy.is_market_open', return_value=True)
@patch('strategies.base_strategy.asyncio.iscoroutinefunction', return_value=False)
async def test_place_order(mock_iscoroutinefunction, mock_is_market_open, strategy):
    strategy.broker.place_order = AsyncMock()
    await strategy.place_order('AAPL', 10, 'buy', 150)
    strategy.broker.place_order.assert_called_once_with('AAPL', 10, 'buy', strategy.strategy_name, 150)
