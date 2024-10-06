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
    mock_should_own.side_effect = [10, 5, 10]

    # Unpack strategy and mock broker
    strategy, mock_broker = strategy_setup
    mock_broker.place_order = AsyncMock()

    # Mock account info
    mock_broker.get_account_info.return_value = {
        'securities_account': {
            'balance': {
                'cash': 10000,
                'total': 100000  # Total balance matches starting capital
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

    mock_balance = MagicMock()
    mock_balance.balance = 10000

    # Mock calculate_target_balances to return 50% cash and 50% investment
    mock_calculate_target_balances.return_value = (5000, 5000)

    # Simulate session.execute() returning a mock result
    mock_result = MagicMock()
    mock_result.scalar.return_value = mock_balance
    mock_session.execute.return_value = mock_result

    # Call rebalance (since this is an async function)
    await strategy.rebalance()

    # TODO: verify/check math here
    mock_broker.place_order.assert_any_call('AAPL', 15 - 10, 'buy', 'constant_percentage', 100)
    mock_broker.place_order.assert_any_call('GOOGL', 10 - 5, 'buy', 'constant_percentage', 200)
    mock_broker.place_order.assert_any_call('MSFT', 15 - 10, 'sell', 'constant_percentage', 150)

    # Verify that the database session commit was called
    mock_session.commit.assert_called_once()

@pytest.mark.asyncio
@patch('strategies.constant_percentage_strategy.ConstantPercentageStrategy.calculate_target_balances')
@patch('strategies.constant_percentage_strategy.ConstantPercentageStrategy.should_own')
@patch('strategies.base_strategy.BaseStrategy.fetch_current_db_positions')
@patch('strategies.base_strategy.is_market_open')
async def test_no_rebalance_needed(mock_is_market_open, mock_current_db_positions, mock_should_own, mock_calculate_target_balances, strategy_setup):
    mock_is_market_open.return_value = True  # Market is open
    # Current positions match target
    mock_current_db_positions.return_value = {
        'AAPL': 15,
        'GOOGL': 10,
        'MSFT': 10
    }

    # Mock should_own return values
    mock_should_own.side_effect = [15, 10, 10]  # Target quantities: AAPL(10), GOOGL(5), MSFT(15)

    # Unpack strategy and mock broker
    strategy, mock_broker = strategy_setup
    mock_broker.place_order = AsyncMock()

    # Mock account info
    mock_broker.get_account_info.return_value = {
        'securities_account': {
            'balance': {
                'cash': 10000,
                'total': 100000  # Total balance matches starting capital
            }
        }
    }

    mock_broker.get_positions.return_value = {
        'AAPL': {'quantity': 15},  # 10 shares owned
        'GOOGL': {'quantity': 10},  # 5 shares owned
        'MSFT': {'quantity': 10}   # 15 shares owned
    }

    # Mock stock prices
    mock_broker.get_current_price.side_effect = lambda symbol: 100 if symbol == 'AAPL' else 200 if symbol == 'GOOGL' else 150

    # Mock session for async database access
    mock_session = AsyncMock()
    strategy.broker.Session.return_value.__aenter__.return_value = mock_session

    mock_balance = MagicMock()
    mock_balance.balance = 10000  # Mock balance

    # Mock calculate_target_balances to return 50% cash and 50% investment
    mock_calculate_target_balances.return_value = (5000, 5000)

    # Simulate session.execute() returning a mock result
    mock_result = MagicMock()
    mock_result.scalar.return_value = mock_balance
    mock_session.execute.return_value = mock_result

    # Call rebalance
    await strategy.rebalance()

    # Ensure that no orders were placed since the target is already met
    mock_broker.place_order.assert_not_called()

@pytest.mark.asyncio
@patch('strategies.constant_percentage_strategy.ConstantPercentageStrategy.calculate_target_balances')
@patch('strategies.constant_percentage_strategy.ConstantPercentageStrategy.should_own')
@patch('strategies.base_strategy.BaseStrategy.fetch_current_db_positions')
@patch('strategies.base_strategy.is_market_open')
async def test_no_rebalance_needed(mock_is_market_open, mock_current_db_positions, mock_should_own, mock_calculate_target_balances, strategy_setup):
    mock_is_market_open.return_value = True  # Market is open
    # Current positions match target
    mock_current_db_positions.return_value = {
        'AAPL': 15,
        'GOOGL': 10,
        'MSFT': 51
    }

    # Mock should_own return values
    mock_should_own.side_effect = [15, 10, 10]  # Target quantities: AAPL(10), GOOGL(5), MSFT(15)

    # Unpack strategy and mock broker
    strategy, mock_broker = strategy_setup
    mock_broker.place_order = AsyncMock()

    # Mock account info
    mock_broker.get_account_info.return_value = {
        'securities_account': {
            'balance': {
                'cash': 10000,
                'total': 100000  # Total balance matches starting capital
            }
        }
    }

    mock_broker.get_positions.return_value = {
        'AAPL': {'quantity': 15},
        'GOOGL': {'quantity': 10},
        'MSFT': {'quantity': 51}
    }

    # Mock stock prices
    mock_broker.get_current_price.side_effect = lambda symbol: 100 if symbol == 'AAPL' else 200 if symbol == 'GOOGL' else 150

    # Mock session for async database access
    mock_session = AsyncMock()
    strategy.broker.Session.return_value.__aenter__.return_value = mock_session

    mock_balance = MagicMock()
    mock_balance.balance = 10000  # Mock balance

    # Mock calculate_target_balances to return 50% cash and 50% investment
    mock_calculate_target_balances.return_value = (5000, 5000)

    # Simulate session.execute() returning a mock result
    mock_result = MagicMock()
    mock_result.scalar.return_value = mock_balance
    mock_session.execute.return_value = mock_result

    # Call rebalance
    await strategy.rebalance()

    # Ensure that no orders were placed since the target is already met
    mock_broker.place_order.assert_any_call('MSFT', 41, 'sell', 'constant_percentage', 150)

@pytest.mark.asyncio
@patch('strategies.constant_percentage_strategy.ConstantPercentageStrategy.calculate_target_balances')
@patch('strategies.constant_percentage_strategy.ConstantPercentageStrategy.should_own')
@patch('strategies.base_strategy.BaseStrategy.fetch_current_db_positions')
@patch('strategies.base_strategy.is_market_open')
async def test_rebalance_with_custom_buffer(mock_is_market_open, mock_current_db_positions, mock_should_own, mock_calculate_target_balances, strategy_setup):
    mock_is_market_open.return_value = True  # Market is open
    # Set up mock current positions in the database
    mock_current_db_positions.return_value = {
        'AAPL': 10,  # 10 shares of AAPL
        'GOOGL': 5,  # 5 shares of GOOGL
        'MSFT': 12   # 15 shares of MSFT
    }

    # Mock return value for should_own (indicating the number of shares we want to own)
    mock_should_own.side_effect = [12, 4, 14]  # Slightly different target quantities: AAPL(12), GOOGL(4), MSFT(14)

    # Unpack strategy and mock broker
    strategy, mock_broker = strategy_setup
    mock_broker.place_order = AsyncMock()

    # Set a custom buffer of 20% (0.2)
    strategy.buffer = 0.25

    # Mock account info
    mock_broker.get_account_info.return_value = {
        'securities_account': {
            'balance': {
                'cash': 10000,
                'total': 100000  # Total balance matches starting capital
            }
        }
    }

    mock_broker.get_positions.return_value = {
        'AAPL': {'quantity': 15},
        'GOOGL': {'quantity': 10},
        'MSFT': {'quantity': 12}
    }

    # Mock stock prices
    mock_broker.get_current_price.side_effect = lambda symbol: 100 if symbol == 'AAPL' else 200 if symbol == 'GOOGL' else 150

    # Mock session for async database access
    mock_session = AsyncMock()
    strategy.broker.Session.return_value.__aenter__.return_value = mock_session

    mock_balance = MagicMock()
    mock_balance.balance = 10000  # Mock balance

    # Mock calculate_target_balances to return 50% cash and 50% investment
    mock_calculate_target_balances.return_value = (5000, 5000)

    # Simulate session.execute() returning a mock result
    mock_result = MagicMock()
    mock_result.scalar.return_value = mock_balance
    mock_session.execute.return_value = mock_result

    # Call rebalance
    await strategy.rebalance()

    # Since the buffer is 20%, and all positions are within the buffer, no orders should be placed
    mock_broker.place_order.assert_not_called()

@pytest.mark.asyncio
@patch('strategies.constant_percentage_strategy.ConstantPercentageStrategy.calculate_target_balances')
@patch('strategies.constant_percentage_strategy.ConstantPercentageStrategy.should_own')
@patch('strategies.base_strategy.BaseStrategy.fetch_current_db_positions')
@patch('strategies.base_strategy.is_market_open')
async def test_rebalance_with_custom_buffer_control(mock_is_market_open, mock_current_db_positions, mock_should_own, mock_calculate_target_balances, strategy_setup):
    mock_is_market_open.return_value = True  # Market is open
    # Set up mock current positions in the database
    mock_current_db_positions.return_value = {
        'AAPL': 10,  # 10 shares of AAPL
        'GOOGL': 5,  # 5 shares of GOOGL
        'MSFT': 12   # 15 shares of MSFT
    }

    # Mock return value for should_own (indicating the number of shares we want to own)
    mock_should_own.side_effect = [12, 4, 14]  # Slightly different target quantities: AAPL(12), GOOGL(4), MSFT(14)

    # Unpack strategy and mock broker
    strategy, mock_broker = strategy_setup
    mock_broker.place_order = AsyncMock()

    # Mock account info
    mock_broker.get_account_info.return_value = {
        'securities_account': {
            'balance': {
                'cash': 10000,
                'total': 100000  # Total balance matches starting capital
            }
        }
    }

    mock_broker.get_positions.return_value = {
        'AAPL': {'quantity': 15},
        'GOOGL': {'quantity': 10},
        'MSFT': {'quantity': 12}
    }

    # Mock stock prices
    mock_broker.get_current_price.side_effect = lambda symbol: 100 if symbol == 'AAPL' else 200 if symbol == 'GOOGL' else 150

    # Mock session for async database access
    mock_session = AsyncMock()
    strategy.broker.Session.return_value.__aenter__.return_value = mock_session

    mock_balance = MagicMock()
    mock_balance.balance = 10000  # Mock balance

    # Mock calculate_target_balances to return 50% cash and 50% investment
    mock_calculate_target_balances.return_value = (5000, 5000)

    # Simulate session.execute() returning a mock result
    mock_result = MagicMock()
    mock_result.scalar.return_value = mock_balance
    mock_session.execute.return_value = mock_result

    # Call rebalance
    await strategy.rebalance()

    # Since the buffer is 20%, and all positions are within the buffer, no orders should be placed
    mock_broker.place_order.assert_any_call('MSFT', 2, 'sell', 'constant_percentage', 150)
