import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from strategies.base_strategy import BaseStrategy
import asyncio
from unittest.mock import AsyncMock
from sqlalchemy import select
from database.models import Balance, Position

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
    mock_balance.balance = 10000  # Set an example balance

    # Simulate session.execute() returning a mock result
    mock_result = AsyncMock()
    mock_result.scalar.return_value = mock_balance
    mock_session.execute.return_value = mock_result

    # Call the initialize_starting_balance method
    await strategy.initialize_starting_balance()

    # Build the expected query
    expected_query = select(Balance).filter_by(
        strategy=strategy.strategy_name,
        broker=strategy.broker.broker_name,
        type='cash'
    )

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
    session_mock = strategy.broker.Session.return_value.__enter__.return_value
    session_mock.query.return_value.filter_by.return_value.first.return_value = None
    await strategy.initialize_starting_balance()
    session_mock.add.assert_called_once()
    session_mock.commit.assert_called_once()

@pytest.mark.asyncio
@patch('strategies.base_strategy.datetime')
@patch('strategies.base_strategy.asyncio.iscoroutinefunction')
@patch('strategies.base_strategy.BaseStrategy.should_own')
async def test_sync_positions_with_broker(mock_should_own, mock_iscoroutinefunction, mock_datetime, strategy):
    mock_should_own.return_value = True
    mock_datetime.utcnow.return_value = datetime(2023, 1, 1)
    strategy.broker.get_positions.return_value = {'AAPL': {'quantity': 10}}
    strategy.broker.get_current_price.return_value = 150
    mock_iscoroutinefunction.return_value = False

    session_mock = strategy.broker.Session.return_value.__enter__.return_value
    session_mock.query.return_value.filter_by.return_value.first.return_value = None
    session_mock.query.return_value.filter_by.return_value.all.return_value = []

    await strategy.sync_positions_with_broker()

    session_mock.add.assert_called_once()
    session_mock.commit.assert_called_once()

def test_calculate_target_balances(strategy):
    total_balance = 10000
    cash_percentage = 0.2
    target_cash_balance, target_investment_balance = strategy.calculate_target_balances(total_balance, cash_percentage)
    assert target_cash_balance == 2000
    assert target_investment_balance == 8000

def test_fetch_current_db_positions(strategy):
    session_mock = strategy.broker.Session.return_value.__enter__.return_value
    session_mock.query.return_value.filter_by.return_value.all.return_value = [
        MagicMock(symbol='AAPL', quantity=10)
    ]
    positions = strategy.fetch_current_db_positions(session_mock)
    assert positions == {'AAPL': 10}

@pytest.mark.asyncio
@patch('strategies.base_strategy.is_market_open', return_value=True)
@patch('strategies.base_strategy.asyncio.iscoroutinefunction', return_value=False)
async def test_place_order(mock_iscoroutinefunction, mock_is_market_open, strategy):
    await strategy.place_order('AAPL', 10, 'buy', 150)
    strategy.broker.place_order.assert_called_once_with('AAPL', 10, 'buy', 'test_strategy', 150)
