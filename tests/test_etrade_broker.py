import unittest
from unittest.mock import patch, MagicMock
from brokers.etrade_broker import EtradeBroker

class TestEtradeBroker(unittest.TestCase):

    @patch('brokers.etrade_broker.requests.get')
    def test_connect(self, mock_get):
        broker = EtradeBroker('api_key', 'secret_key')
        broker.connect()
        self.assertTrue(hasattr(broker, 'auth'))

    @patch('brokers.etrade_broker.requests.get')
    def test_get_account_info(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'accountListResponse': {'accounts': [{'accountId': '12345'}]}
        }
        mock_get.return_value = mock_response

        broker = EtradeBroker('api_key', 'secret_key')
        broker.connect()
        account_info = broker.get_account_info()
        self.assertEqual(account_info, {
            'accountListResponse': {'accounts': [{'accountId': '12345'}]}
        })
        self.assertEqual(broker.account_id, '12345')

    @patch('brokers.etrade_broker.requests.post')
    @patch('brokers.etrade_broker.EtradeBroker.get_account_info')
    def test_place_order(self, mock_get_account_info, mock_post):
        mock_get_account_info.return_value = {
            'accountListResponse': {'accounts': [{'accountId': '12345'}]}
        }
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'filled'}
        mock_post.return_value = mock_response

        broker = EtradeBroker('api_key', 'secret_key')
        broker.connect()
        broker.get_account_info()
        order_info = broker.place_order('AAPL', 10, 'buy', 'example_strategy', 150.00)
        self.assertEqual(order_info, {'status': 'filled'})

    @patch('brokers.etrade_broker.requests.get')
    def test_get_order_status(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'completed'}
        mock_get.return_value = mock_response

        broker = EtradeBroker('api_key', 'secret_key')
        broker.connect()
        order_status = broker.get_order_status('order_id')
        self.assertEqual(order_status, {'status': 'completed'})

    @patch('brokers.etrade_broker.requests.put')
    def test_cancel_order(self, mock_put):
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'cancelled'}
        mock_put.return_value = mock_response

        broker = EtradeBroker('api_key', 'secret_key')
        broker.connect()
        cancel_status = broker.cancel_order('order_id')
        self.assertEqual(cancel_status, {'status': 'cancelled'})

    @patch('brokers.etrade_broker.requests.get')
    def test_get_options_chain(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {'options': 'chain'}
        mock_get.return_value = mock_response

        broker = EtradeBroker('api_key', 'secret_key')
        broker.connect()
        options_chain = broker.get_options_chain('AAPL', '2024-12-20')
        self.assertEqual(options_chain, {'options': 'chain'})

if __name__ == '__main__':
    unittest.main()
