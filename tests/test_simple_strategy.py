import pytest
from unittest.mock import AsyncMock, MagicMock
from strategies.simple_strategy import SimpleStrategy

@pytest.fixture
def broker():
    broker = MagicMock()
    broker.get_account_info = AsyncMock(return_value={'buying_power': 20000})
    broker.get_positions = AsyncMock(return_value={})
    broker.get_current_price = AsyncMock(return_value=100)
    return broker

@pytest.fixture
def strategy(broker):
    return SimpleStrategy(broker, buy_threshold=100, sell_threshold=150)

@pytest.mark.asyncio
async def test_should_buy():
    broker = MagicMock()
    strategy = SimpleStrategy(broker, buy_threshold=100, sell_threshold=150)

    assert await strategy.should_buy('AAPL', 90) == True
    assert await strategy.should_buy('AAPL', 110) == False

@pytest.mark.asyncio
async def test_should_sell():
    broker = MagicMock()
    strategy = SimpleStrategy(broker, buy_threshold=100, sell_threshold=150)

    assert await strategy.should_sell('AAPL', 160) == True
    assert await strategy.should_sell('AAPL', 140) == False

@pytest.mark.asyncio
async def test_rebalance(strategy):
    # Mock the broker methods
    strategy.broker.get_positions.return_value = {'AAPL': {'quantity': 10}}
    strategy.broker.get_current_price.return_value = 160  # Above sell threshold
    strategy.place_order = AsyncMock()

    await strategy.rebalance()

    # Verify that a sell order was placed
    strategy.place_order.assert_called_once_with('AAPL', 10, 'sell', 160)
