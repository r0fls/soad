import pytest
from unittest.mock import MagicMock
from datetime import timedelta
from strategies.constant_percentage_strategy import ConstantPercentageStrategy
from unittest.mock import AsyncMock, patch

@pytest.fixture
def strategy_setup():
    # Mock broker object setup
    mock_broker = MagicMock()
    stock_allocations = {'AAPL': 0.3, 'GOOGL': 0.4, 'MSFT': 0.3}
    cash_percentage = 0.2
    rebalance_interval_minutes = 60
    starting_capital = 10000

    # Create the strategy object
    strategy = ConstantPercentageStrategy(
        broker=mock_broker,
        strategy_name="constant_percentage",
        stock_allocations=stock_allocations,
        cash_percentage=cash_percentage,
        rebalance_interval_minutes=rebalance_interval_minutes,
        starting_capital=starting_capital
    )
    return strategy, mock_broker

def test_initialization(strategy_setup):
    strategy, mock_broker = strategy_setup
    assert strategy.stock_allocations == {'AAPL': 0.3, 'GOOGL': 0.4, 'MSFT': 0.3}
    assert strategy.cash_percentage == 0.2
    assert strategy.rebalance_interval == timedelta(minutes=60)
    assert strategy.starting_capital == 10000

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.asyncio
@patch('strategies.constant_percentage_strategy.ConstantPercentageStrategy.calculate_target_balances')
@patch('strategies.constant_percentage_strategy.ConstantPercentageStrategy.should_own')
@patch('strategies.base_strategy.BaseStrategy.fetch_current_db_positions')
@patch('strategies.base_strategy.is_market_open')
async def test_rebalance(mock_is_market_open, mock_current_db_positions, mock_should_own, mock_calculate_target_balances, strategy_setup):
    mock_is_market_open.return_value = True  # Market is open
    # Set up mock current positions in the database
    mock_current_db_positions.return_value = {
        'AAPL': 10,  # 10 shares of AAPL
        'GOOGL': 5,  # 5 shares of GOOGL
        'MSFT': 15   # 15 shares of MSFT
    }

    # Mock return value for should_own (indicating the number of shares we want to own)
    mock_should_own.side_effect = [20, 10, 15]  # Target quantities: AAPL(20), GOOGL(10), MSFT(15)

    # Unpack strategy and mock broker
    strategy, mock_broker = strategy_setup
    mock_broker.place_order = AsyncMock()

    # Mock account info
    mock_broker.get_account_info.return_value = {
        'securities_account': {
            'balance': {
                'cash': 1000,
                'total': 10000  # Total balance matches starting capital
            }
        }
    }

    # Mock stock prices
    mock_broker.get_current_price.side_effect = lambda symbol: 100 if symbol == 'AAPL' else 200 if symbol == 'GOOGL' else 150

    # Mock current positions in the broker (what we actually own)
    mock_broker.get_positions.return_value = {
        'AAPL': {'quantity': 10},  # 10 shares owned
        'GOOGL': {'quantity': 5},  # 5 shares owned
        'MSFT': {'quantity': 15}   # 15 shares owned
    }

    # Mock session for async database access
    mock_session = AsyncMock()
    strategy.broker.Session.return_value.__aenter__.return_value = mock_session

    # Create a mock balance object
    mock_balance = MagicMock()
    mock_balance.balance = 1000  # Mock example balance

    # Mock calculate_target_balances to return 50% cash and 50% investment
    mock_calculate_target_balances.return_value = (500, 500)

    # Simulate session.execute() returning a mock result
    mock_result = MagicMock()
    mock_result.scalar.return_value = mock_balance
    mock_session.execute.return_value = mock_result

    # Call rebalance (since this is an async function)
    await strategy.rebalance()

    # TODO: verify/check math here
    mock_broker.place_order.assert_any_call('AAPL', 10 - 1, 'sell', 100)  # Buy 10 AAPL shares
    mock_broker.place_order.assert_any_call('GOOGL', 5 - 1, 'sell', 200)  # Buy 5 GOOGL shares
    mock_broker.place_order.assert_any_call('MSFT', 15 - 1, 'sell', 150)  # No action for MSFT, still checked

    # Verify that the database session commit was called
    mock_session.commit.assert_called_once()
