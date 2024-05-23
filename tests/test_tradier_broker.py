import unittest
from unittest.mock import patch, MagicMock
from brokers.tradier_broker import TradierBroker

class TestTradierBroker(unittest.TestCase):

    @patch('brokers.tradier_broker.requests.post')
    def test_connect(self, mock_post):
        broker = TradierBroker('api_key', 'secret_key')
        broker.connect()
        self.assertTrue(hasattr(broker, 'headers'))

    @patch('brokers.tradier_broker.requests.get')
    def test_get_account_info(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {'account': 'info'}
        mock_get.return_value = mock_response

        broker = TradierBroker('api_key', 'secret_key')
        broker.connect()
        account_info = broker.get_account_info()
        self.assertEqual(account_info, {'account': 'info'})

    @patch('brokers.tradier_broker.requests.post')
    def test_place_order(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'filled'}
        mock_post.return_value = mock_response

        broker = TradierBroker('api_key', 'secret_key')
        broker.connect()
        order_info = broker.place_order('AAPL', 10, 'buy', 'example_strategy', 150.00)
        self.assertEqual(order_info, {'status': 'filled'})

    @patch('brokers.tradier_broker.requests.get')
    def test_get_order_status(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'completed'}
        mock_get.return_value = mock_response

        broker = TradierBroker('api_key', 'secret_key')
        broker.connect()
        order_status = broker.get_order_status('order_id')
        self.assertEqual(order_status, {'status': 'completed'})

    @patch('brokers.tradier_broker.requests.delete')
    def test_cancel_order(self, mock_delete):
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'cancelled'}
        mock_delete.return_value = mock_response

        broker = TradierBroker('api_key', 'secret_key')
        broker.connect()
        cancel_status = broker.cancel_order('order_id')
        self.assertEqual(cancel_status, {'status': 'cancelled'})

    @patch('brokers.tradier_broker.requests.get')
    def test_get_options_chain(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {'options': 'chain'}
        mock_get.return_value = mock_response

        broker = TradierBroker('api_key', 'secret_key')
        broker.connect()
        options_chain = broker.get_options_chain('AAPL', '2024-12-20')
        self.assertEqual(options_chain, {'options': 'chain'})

if __name__ == '__main__':
    unittest.main()
