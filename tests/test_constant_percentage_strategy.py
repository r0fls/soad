import unittest
from unittest.mock import MagicMock
from datetime import timedelta
from strategies.constant_percentage_strategy import ConstantPercentageStrategy

class TestConstantPercentageStrategy(unittest.TestCase):

    # TODO: fix
    def skip_setUp(self):
        self.mock_broker = MagicMock()
        self.stock_allocations = {'AAPL': 0.3, 'GOOGL': 0.4, 'MSFT': 0.3}
        self.cash_percentage = 0.2
        self.rebalance_interval_minutes = 60
        self.starting_capital = 10000
        self.strategy = ConstantPercentageStrategy(
            broker=self.mock_broker,
            stock_allocations=self.stock_allocations,
            cash_percentage=self.cash_percentage,
            rebalance_interval_minutes=self.rebalance_interval_minutes,
            starting_capital=self.starting_capital
        )

    def skip_test_initialization(self):
        self.assertEqual(self.strategy.stock_allocations, self.stock_allocations)
        self.assertEqual(self.strategy.cash_percentage, self.cash_percentage)
        self.assertEqual(self.strategy.rebalance_interval, timedelta(minutes=self.rebalance_interval_minutes))
        self.assertEqual(self.strategy.starting_capital, self.starting_capital)

    # TODO: fix
    def skip_test_rebalance(self):
        self.mock_broker.get_account_info.return_value = {
            'securities_account': {
                'balance': {
                    'cash': 1000,
                    'total': 10000  # Mock the total to match starting capital
                }
            }
        }
        self.mock_broker.get_current_price.side_effect = lambda symbol: 100 if symbol == 'AAPL' else 200 if symbol == 'GOOGL' else 150
        self.mock_broker.get_positions.return_value = [
            {'symbol': 'AAPL', 'quantity': 10},
            {'symbol': 'GOOGL', 'quantity': 5},
            {'symbol': 'MSFT', 'quantity': 15}
        ]

        self.strategy.rebalance()

        self.mock_broker.place_order.assert_any_call('AAPL', 20 - 10, 'buy', 'constant_percentage')
        self.mock_broker.place_order.assert_any_call('GOOGL', 20 - 5, 'buy', 'constant_percentage')
        self.mock_broker.place_order.assert_any_call('MSFT', 13 - 15, 'sell', 'constant_percentage')

if __name__ == '__main__':
    unittest.main()
