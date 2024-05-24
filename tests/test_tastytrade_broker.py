import unittest
from unittest.mock import patch, MagicMock
from brokers.tastytrade_broker import TastytradeBroker

class TestTastytradeBroker(unittest.TestCase):

    def setUp(self):
        self.broker = TastytradeBroker('api_key', 'secret_key')

    def mock_connect(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': {'session-token': 'token'}}
        mock_post.return_value = mock_response

    @patch('brokers.tastytrade_broker.requests.post')
    def test_connect(self, mock_post):
        self.mock_connect(mock_post)
        self.broker.connect()
        self.assertTrue(hasattr(self.broker, 'session_token'))
        self.assertTrue(hasattr(self.broker, 'headers'))

    @patch('brokers.tastytrade_broker.requests.get')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_get_account_info(self, mock_post, mock_get):
        self.mock_connect(mock_post)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'data': {'items': [{'account': {'account_number': '12345'}}]}
        }
        mock_get.return_value = mock_response

        self.broker.connect()
        account_info = self.broker.get_account_info()
        self.assertEqual(account_info, {
            'data': {'items': [{'account': {'account_number': '12345'}}]}
        })
        self.assertEqual(self.broker.account_id, '12345')

    @patch('brokers.tastytrade_broker.requests.get')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_place_order(self, mock_post, mock_get_account_info):
        # Mock the connect method
        mock_connect_response = MagicMock()
        mock_connect_response.status_code = 200
        mock_connect_response.json.return_value = {'data': {'session-token': 'token'}}
        mock_post.side_effect = [mock_connect_response, mock_connect_response]
        self.broker.connect()
        
        # Mock the get_account_info method
        mock_get_account_info_response = MagicMock()
        mock_get_account_info_response.json.return_value = {
            'data': {'items': [{'account': {'account_number': '12345'}}]}
        }
        mock_get_account_info.return_value = mock_get_account_info_response

        # Mock the place_order method
        mock_place_order_response = MagicMock()
        mock_place_order_response.json.return_value = {'status': 'filled'}
        mock_post.side_effect = [mock_place_order_response]

        self.broker.get_account_info()
        order_info = self.broker.place_order('AAPL', 10, 'buy', 'example_strategy', 150.00)
        self.assertEqual(order_info, {'status': 'filled'})

    @patch('brokers.tastytrade_broker.requests.get')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_get_order_status(self, mock_post_connect, mock_get):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'completed'}
        mock_get.return_value = mock_response

        self.broker.connect()
        order_status = self.broker.get_order_status('order_id')
        self.assertEqual(order_status, {'status': 'completed'})

    @patch('brokers.tastytrade_broker.requests.delete')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_cancel_order(self, mock_post_connect, mock_delete):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'cancelled'}
        mock_delete.return_value = mock_response

        self.broker.connect()
        cancel_status = self.broker.cancel_order('order_id')
        self.assertEqual(cancel_status, {'status': 'cancelled'})

    @patch('brokers.tastytrade_broker.requests.get')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_get_options_chain(self, mock_post_connect, mock_get):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {'options': 'chain'}
        mock_get.return_value = mock_response

        self.broker.connect()
        options_chain = self.broker.get_options_chain('AAPL', '2024-12-20')
        self.assertEqual(options_chain, {'options': 'chain'})

if __name__ == '__main__':
    unittest.main()
