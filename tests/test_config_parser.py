import pytest
from unittest.mock import patch, MagicMock
from utils.config import initialize_brokers, initialize_strategies
import yaml

@pytest.fixture
def config():
    return """
    brokers:
      tradier:
        type: "tradier"
        api_key: "your_tradier_api_key"
      tastytrade:
        type: "tastytrade"
        username: "your_tastytrade_username"
        password: "password"
    strategies:
      - type: "constant_percentage"
        broker: "tradier"
        starting_capital: 10000
        stock_allocations:
          AAPL: 0.3
          GOOGL: 0.4
          MSFT: 0.3
        cash_percentage: 0.2
        rebalance_interval_minutes: 60
      - type: "custom"
        broker: "tastytrade"
        starting_capital: 5000
        file: "custom_strategies/my_custom_strategy.py"
        className: "MyCustomStrategy"
        stock_allocations:
          AAPL: 0.3
          GOOGL: 0.4
          MSFT: 0.3
        cash_percentage: 0.2
        rebalance_interval_minutes: 60
    """

@patch('utils.config.TradierBroker')
@patch('utils.config.TastytradeBroker')
def test_initialize_brokers(MockTastytradeBroker, MockTradierBroker, config):
    mock_broker_tradier = MagicMock()
    mock_broker_tastytrade = MagicMock()
    MockTradierBroker.return_value = mock_broker_tradier
    MockTastytradeBroker.return_value = mock_broker_tastytrade

    parsed_config = yaml.safe_load(config)
    brokers = initialize_brokers(parsed_config)

    assert brokers == {'tradier': mock_broker_tradier, 'tastytrade': mock_broker_tastytrade}
    MockTradierBroker.assert_called_once()
    MockTastytradeBroker.assert_called_once()

@patch('utils.config.load_strategy_class')
@patch('strategies.constant_percentage_strategy.ConstantPercentageStrategy', autospec=True)
@pytest.mark.skip(reason="Still requires fixing the TODOs")
def test_initialize_strategies(MockConstantPercentageStrategy, mock_load_strategy_class, config):
    mock_strategy_constant = MagicMock()
    mock_strategy_custom = MagicMock()
    MockConstantPercentageStrategy.return_value = mock_strategy_constant

    parsed_config = yaml.safe_load(config)
    brokers = {'tradier': MagicMock(), 'tastytrade': MagicMock()}
    strategies = initialize_strategies(brokers, parsed_config)

    assert len(strategies) == 2
    # TODO: Fix these assertions based on actual arguments being passed.
    # MockConstantPercentageStrategy.assert_called_once_with(
    #     broker=brokers['tradier'],
    #     stock_allocations={'AAPL': 0.3, 'GOOGL': 0.4, 'MSFT': 0.3},
    #     cash_percentage=0.2,
    #     rebalance_interval_minutes=60,
    #     starting_capital=10000
    # )
    mock_load_strategy_class.assert_any_call(
        'custom_strategies/my_custom_strategy.py', 'MyCustomStrategy'
    )
    # TODO: Fix this assertion after refining the mock strategy call.
    # mock_strategy_custom.assert_called_once_with(
    #     broker=brokers['tastytrade'],
    #     stock_allocations={'AAPL': 0.3, 'GOOGL': 0.4, 'MSFT': 0.3},
    #     cash_percentage=0.2,
    #     rebalance_interval_minutes=60,
    #     starting_capital=5000
    # )