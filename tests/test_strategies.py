import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from strategies.base_strategy import BaseStrategy
import asyncio

class TestBaseStrategy(BaseStrategy):
    def __init__(self, broker):
        super().__init__(broker, 'test_strategy', 10000)

    async def rebalance(self):
        pass

class TestBaseStrategyMethods(unittest.TestCase):

    def setUp(self):
        self.broker = MagicMock()

        # Mock get_account_info to return a dictionary with an integer buying_power
        self.broker.get_account_info.return_value = {'buying_power': 20000}

        # Mock Session and its return value
        session_mock = MagicMock()
        self.broker.Session.return_value.__enter__.return_value = session_mock

        # Mock query result for Balance
        balance_mock = MagicMock()
        balance_mock.balance = 10000
        session_mock.query.return_value.filter_by.return_value.first.return_value = balance_mock

        # Initialize the strategy after setting up the mocks
        self.strategy = TestBaseStrategy(self.broker)

    def test_initialize_starting_balance_existing(self):
        self.strategy.initialize_starting_balance()
        self.broker.Session.return_value.__enter__.return_value.add.assert_not_called()
        self.broker.Session.return_value.__enter__.return_value.commit.assert_not_called()

    def test_initialize_starting_balance_new(self):
        self.broker.Session.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = None
        self.strategy.initialize_starting_balance()
        self.broker.Session.return_value.__enter__.return_value.add.assert_called_once()
        self.broker.Session.return_v

    @patch('strategies.base_strategy.datetime')
    @patch('strategies.base_strategy.asyncio.iscoroutinefunction')
    @patch('strategies.base_strategy.BaseStrategy.should_own')
    def test_sync_positions_with_broker(self, mock_should_own, mock_iscoroutinefunction, mock_datetime):
        mock_should_own.return_value = True
        mock_datetime.utcnow.return_value = datetime(2023, 1, 1)
        self.broker.get_positions.return_value = {'AAPL': {'quantity': 10}}
        self.broker.get_current_price.return_value = 150
        mock_iscoroutinefunction.return_value = False

        session_mock = self.broker.Session.return_value.__enter__.return_value
        session_mock.query.return_value.filter_by.return_value.first.return_value = None
        session_mock.query.return_value.filter_by.return_value.all.return_value = []

        asyncio.run(self.strategy.sync_positions_with_broker())

        session_mock.add.assert_called_once()
        session_mock.commit.assert_called_once()

    def test_calculate_target_balances(self):
        total_balance = 10000
        cash_percentage = 0.2
        target_cash_balance, target_investment_balance = self.strategy.calculate_target_balances(total_balance, cash_percentage)
        self.assertEqual(target_cash_balance, 2000)
        self.assertEqual(target_investment_balance, 8000)

    def test_fetch_current_db_positions(self):
        session_mock = self.broker.Session.return_value.__enter__.return_value
        session_mock.query.return_value.filter_by.return_value.all.return_value = [
            MagicMock(symbol='AAPL', quantity=10)
        ]
        positions = self.strategy.fetch_current_db_positions(session_mock)
        self.assertEqual(positions, {'AAPL': 10})


    @patch('utils.utils.is_market_open', return_value=True)
    @patch('strategies.base_strategy.asyncio.iscoroutinefunction', return_value=False)
    async def test_place_order(self, mock_iscoroutinefunction, mock_is_market_open):
        await asyncio.run(self.strategy.place_order('AAPL', 10, 'buy'))
        self.broker.place_order.assert_called_once_with('AAPL', 10, 'buy', 'test_strategy')


if __name__ == '__main__':
    unittest.main()
