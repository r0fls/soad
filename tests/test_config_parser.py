import unittest
from unittest.mock import patch, MagicMock
from utils.config import parse_config, initialize_brokers, initialize_strategies
import yaml

class TestConfigParser(unittest.TestCase):

    def setUp(self):
        self.config = """
        brokers:
          tradier:
            type: "tradier"
            api_key: "your_tradier_api_key"
          tastytrade:
            type: "tastytrade"
            api_key: "your_tastytrade_api_key"
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
    def test_initialize_brokers(self, MockTastytradeBroker, MockTradierBroker):
        mock_broker_tradier = MagicMock()
        mock_broker_tastytrade = MagicMock()
        MockTradierBroker.return_value = mock_broker_tradier
        MockTastytradeBroker.return_value = mock_broker_tastytrade
        config = yaml.safe_load(self.config)
        brokers = initialize_brokers(config)
        self.assertEqual(brokers, {'tradier': mock_broker_tradier, 'tastytrade': mock_broker_tastytrade})
        MockTradierBroker.assert_called_with(api_key='your_tradier_api_key', secret_key=None)
        MockTastytradeBroker.assert_called_with(api_key='your_tastytrade_api_key', secret_key=None)

    @patch('utils.config.load_strategy_class')
    @patch('strategies.constant_percentage_strategy.ConstantPercentageStrategy')
    def test_initialize_strategies(self, MockConstantPercentageStrategy, mock_load_strategy_class):
        mock_strategy_constant = MagicMock()
        mock_strategy_custom = MagicMock()
        MockConstantPercentageStrategy.return_value = mock_strategy_constant
        mock_load_strategy_class.return_value = mock_strategy_custom
        config = yaml.safe_load(self.config)
        brokers = {'tradier': MagicMock(), 'tastytrade': MagicMock()}
        strategies = initialize_strategies(brokers, config)
        self.assertEqual(strategies, [mock_strategy_constant, mock_strategy_custom])
        MockConstantPercentageStrategy.assert_called_with(
            broker=brokers['tradier'],
            stock_allocations={'AAPL': 0.3, 'GOOGL': 0.4, 'MSFT': 0.3},
            cash_percentage=0.2,
            rebalance_interval_minutes=60,
            starting_capital=10000
        )
        mock_load_strategy_class.assert_called_with(
            'custom_strategies/my_custom_strategy.py', 'MyCustomStrategy'
        )
        mock_strategy_custom.assert_called_with(
            broker=brokers['tastytrade'],
            stock_allocations={'AAPL': 0.3, 'GOOGL': 0.4, 'MSFT': 0.3},
            cash_percentage=0.2,
            rebalance_interval_minutes=60,
            starting_capital=5000
        )

if __name__ == '__main__':
    unittest.main()
