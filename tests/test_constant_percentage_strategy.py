import pytest
from unittest.mock import MagicMock
from datetime import timedelta
from strategies.constant_percentage_strategy import ConstantPercentageStrategy

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

@pytest.mark.asyncio
async def test_rebalance(strategy_setup):
    strategy, mock_broker = strategy_setup

    # Mock account info
    mock_broker.get_account_info.return_value = {
        'securities_account': {
            'balance': {
                'cash': 1000,
                'total': 10000  # Mock the total to match starting capital
            }
        }
    }

    # Mock current prices for stocks
    mock_broker.get_current_price.side_effect = lambda symbol: 100 if symbol == 'AAPL' else 200 if symbol == 'GOOGL' else 150

    # Mock current positions
    mock_broker.get_positions.return_value = {
        'AAPL': {'quantity': 10},
        'GOOGL': {'quantity': 5},
        'MSFT': {'quantity': 15}
    }

    # Call rebalance (use await since rebalance is async)
    await strategy.rebalance()

    # Check if correct orders were placed
    mock_broker.place_order.assert_any_call('AAPL', 20 - 10, 'buy', 100)
    mock_broker.place_order.assert_any_call('GOOGL', 20 - 5, 'buy', 200)
    mock_broker.place_order.assert_any_call('MSFT', 13 - 15, 'sell', 150)
