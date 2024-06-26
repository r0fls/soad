import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from database.models import Trade, Balance, Position
from .base_test import BaseTest
from brokers.base_broker import BaseBroker

class MockBroker(BaseBroker):
    def connect(self):
        pass

    def _get_account_info(self):
        return {'profile': {'account': {'account_number': '12345', 'value': 10000.0}}}

    def _place_option_order(self, symbol, quantity, order_type, price=None):
        return {'status': 'filled', 'filled_price': 150.0}

    def _place_order(self, symbol, quantity, order_type, price=None):
        return {'status': 'filled', 'filled_price': 150.0}

    def _get_order_status(self, order_id):
        return {'status': 'completed'}

    def _cancel_order(self, order_id):
        return {'status': 'cancelled'}

    def _get_options_chain(self, symbol, expiration_date):
        return {'options': 'chain'}

    def get_current_price(self, symbol):
        return 150.0

    def execute_trade(self, *args):
        pass

class TestTrading(BaseTest):
    def setUp(self):
        super().setUp()  # Call the setup from BaseTes

        self.mock_engine = MagicMock()
        self.broker = MockBroker(api_key="dummy_api_key", secret_key="dummy_secret_key", broker_name="dummy_broker", engine=self.mock_engine, prevent_day_trading=True)
        self.broker.Session = MagicMock()
        self.session = self.broker.Session.return_value.__enter__.return_value


        # Additional setup
        additional_fake_trades = [
            Trade(symbol='MSFT', quantity=8, price=200.0, executed_price=202.0, order_type='buy', status='executed', timestamp=datetime.now(timezone.utc), broker='Tastytrade', strategy='RSI', profit_loss=16.0, success='yes'),
        ]
        self.session.add_all(additional_fake_trades)
        self.session.commit()

    def skip_test_execute_trade(self):
        # Example trade data
        trade_data = {
            'symbol': 'AAPL',
            'quantity': 10,
            'price': 150.0,
            'executed_price': 151.0,
            'order_type': 'buy',
            'status': 'executed',
            'timestamp': datetime.now(timezone.utc),
            'broker': 'E*TRADE',
            'strategy': 'SMA',
            'profit_loss': 10.0,
            'success': 'yes'
        }

        # Execute the trade
        broker = MockBroker('api_key', 'secret_key', 'E*TRADE', engine=self.engine)
        broker.execute_trade(self.session, trade_data)

        # Verify the trade was inserted
        trade = self.session.query(Trade).filter_by(symbol='AAPL').first()
        self.assertIsNotNone(trade)

        # Verify the balance was updated
        balance = self.session.query(Balance).filter_by(broker='E*TRADE', strategy='SMA').first()
        self.assertIsNotNone(balance)
        self.assertEqual(balance.total_balance, 1510.0)

    def test_has_bought_today(self):
        today = datetime.now().date()
        self.session.query.return_value.filter.return_value.all.return_value = [
            Trade(symbol="AAPL", timestamp=today)
        ]

        result = self.broker.has_bought_today("AAPL")
        self.assertTrue(result)

        self.session.query.return_value.filter.return_value.all.return_value = []
        result = self.broker.has_bought_today("AAPL")
        self.assertFalse(result)

    def test_update_positions_buy(self):
        trade = Trade(symbol="AAPL", quantity=10, executed_price=150.0, order_type="buy", timestamp=datetime.now())
        self.session.query.return_value.filter_by.return_value.first.return_value = None

        self.broker.update_positions(self.session, trade)
        self.session.add.assert_called_once()

        position = self.session.add.call_args[0][0]
        self.assertEqual(position.symbol, "AAPL")
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.latest_price, 150.0)

    def test_update_positions_sell(self):
        trade = Trade(symbol="AAPL", quantity=5, executed_price=155.0, order_type="sell", timestamp=datetime.now())
        existing_position = Position(symbol="AAPL", broker="dummy_broker", quantity=10, latest_price=150.0)
        self.session.query.return_value.filter_by.return_value.first.return_value = existing_position

        self.broker.update_positions(self.session, trade)
        self.session.commit.assert_called()

        self.assertEqual(existing_position.quantity, 5)
        self.assertEqual(existing_position.latest_price, 155.0)

if __name__ == '__main__':
    unittest.main()
