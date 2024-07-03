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

    @patch('requests.get')
    def test_get_account_info(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "accounts": [{"accountId": "test_account_id"}],
            "cashBalance": 1000.0,
            "buyingPower": 2000.0,
            "netAccountValue": 3000.0,
            "accountType": "CASH"
        }
        mock_get.return_value = mock_response

        account_info = self.broker._get_account_info()
        self.assertEqual(account_info['account_number'], 'test_account_id')
        self.assertEqual(account_info['account_type'], 'CASH')
        self.assertEqual(account_info['buying_power'], 2000.0)
        self.assertEqual(account_info['cash'], 1000.0)
        self.assertEqual(account_info['value'], 3000.0)

    @patch('requests.get')
    def test_get_positions(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "positions": [
                {"ticker": {"symbol": "AAPL"}, "quantity": 10},
                {"ticker": {"symbol": "GOOG"}, "quantity": 5}
            ]
        }
        mock_get.return_value = mock_response

        positions = self.broker.get_positions()
        self.assertIn('AAPL', positions)
        self.assertIn('GOOG', positions)
        self.assertEqual(positions['AAPL']['quantity'], 10)
        self.assertEqual(positions['GOOG']['quantity'], 5)

    @pytest.mark.asyncio
    @patch('requests.get')
    @patch('requests.post')
    async def test_place_order(self, mock_post, mock_get):
        mock_get_response = Mock()
        mock_get_response.raise_for_status = Mock()
        mock_get_response.json.return_value = {
            "data": [{"bidPrice": 100.0, "askPrice": 102.0}]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = Mock()
        mock_post_response.raise_for_status = Mock()
        mock_post_response.json.return_value = {
            "orderId": "test_order_id",
            "filledPrice": 101.0
        }
        mock_post.return_value = mock_post_response

        order = self.broker._place_order("AAPL", 10, "buy")
        self.assertEqual(order['filledPrice'], 101.0)
        self.assertEqual(order['orderId'], "test_order_id")

    @patch('requests.get')
    def test_get_current_price(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "data": [{"lastPrice": 150.0}]
        }
        mock_get.return_value = mock_response

        price = self.broker.get_current_price("AAPL")
        self.assertEqual(price, 150.0)

    @patch('requests.get')
    def test_get_order_status(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "orderId": "test_order_id",
            "status": "Filled"
        }
        mock_get.return_value = mock_response

        status = self.broker._get_order_status("test_order_id")
        self.assertEqual(status['orderId'], "test_order_id")
        self.assertEqual(status['status'], "Filled")

    @patch('requests.delete')
    def test_cancel_order(self, mock_delete):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "orderId": "test_order_id",
            "status": "Cancelled"
        }
        mock_delete.return_value = mock_response

        status = self.broker._cancel_order("test_order_id")
        self.assertEqual(status['orderId'], "test_order_id")
        self.assertEqual(status['status'], "Cancelled")

if __name__ == '__main__':
    unittest.main()
