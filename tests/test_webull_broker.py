import unittest
from unittest.mock import patch, Mock
from brokers.webull_broker import WebullBroker
import pytest

class TestWebullBroker(unittest.TestCase):

    def setUp(self):
        self.api_key = "test_api_key"
        self.secret_key = "test_secret_key"
        self.engine = Mock()
        self.broker = WebullBroker(self.api_key, self.secret_key, self.engine)
        self.broker.account_id = "test_account_id"  # Mock account id for testing

    @patch('webull.webull.get_account')
    def test_get_account_info(self, mock_get_account):
        mock_get_account.return_value = {
            "secAccountId": "test_account_id",
            "cashBalance": 1000.0,
            "buyingPower": 2000.0,
            "totalAccountValue": 3000.0,
            "accountType": "CASH"
        }

        account_info = self.broker._get_account_info()
        self.assertEqual(account_info['account_number'], 'test_account_id')
        self.assertEqual(account_info['account_type'], 'CASH')
        self.assertEqual(account_info['buying_power'], 2000.0)
        self.assertEqual(account_info['cash'], 1000.0)
        self.assertEqual(account_info['value'], 3000.0)

    @patch('webull.webull.get_positions')
    def test_get_positions(self, mock_get_positions):
        mock_get_positions.return_value = [
            {"ticker": {"symbol": "AAPL"}, "quantity": 10},
            {"ticker": {"symbol": "GOOG"}, "quantity": 5}
        ]

        positions = self.broker.get_positions()
        self.assertIn('AAPL', positions)
        self.assertIn('GOOG', positions)
        self.assertEqual(positions['AAPL']['quantity'], 10)
        self.assertEqual(positions['GOOG']['quantity'], 5)

    @pytest.mark.asyncio
    @patch('webull.webull.get_quote')
    @patch('webull.webull.place_order')
    async def test_place_order(self, mock_place_order, mock_get_quote):
        mock_get_quote.return_value = {
            "bidPrice": 100.0,
            "askPrice": 102.0
        }

        mock_place_order.return_value = {
            "orderId": "test_order_id",
            "filledPrice": 101.0
        }

        order = self.broker._place_order("AAPL", 10, "buy")
        self.assertEqual(order['filledPrice'], 101.0)
        self.assertEqual(order['order_id'], "test_order_id")

    @patch('webull.webull.get_quote')
    def test_get_current_price(self, mock_get_quote):
        mock_get_quote.return_value = {
            "lastPrice": 150.0
        }

        price = self.broker.get_current_price("AAPL")
        self.assertEqual(price, 150.0)

    @patch('webull.webull.get_order_status')
    def test_get_order_status(self, mock_get_order_status):
        mock_get_order_status.return_value = {
            "orderId": "test_order_id",
            "status": "Filled"
        }

        status = self.broker._get_order_status("test_order_id")
        self.assertEqual(status['orderId'], "test_order_id")
        self.assertEqual(status['status'], "Filled")

    @patch('webull.webull.cancel_order')
    def test_cancel_order(self, mock_cancel_order):
        mock_cancel_order.return_value = {
            "orderId": "test_order_id",
            "status": "Cancelled"
        }

        status = self.broker._cancel_order("test_order_id")
        self.assertEqual(status['orderId'], "test_order_id")
        self.assertEqual(status['status'], "Cancelled")

if __name__ == '__main__':
    unittest.main()
