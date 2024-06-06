import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from brokers.etrade_broker import EtradeBroker
from .base_test import BaseTest
from database.models import Balance, Trade

class TestEtradeBroker(BaseTest):

    def setUp(self):
        super().setUp()  # Call the setup from BaseTest
        self.broker = EtradeBroker('api_key', 'secret_key', self.engine)

    def mock_connect(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'access_token': 'token'}
        mock_post.return_value = mock_response

    @patch('brokers.etrade_broker.requests.get')
    @patch('brokers.etrade_broker.requests.post')
    def test_connect(self, mock_post, mock_get):
        self.mock_connect(mock_post)
        self.broker.connect()
        self.assertTrue(hasattr(self.broker, 'auth'))


    @patch('brokers.etrade_broker.requests.get')
    @patch('brokers.etrade_broker.requests.post')
    def test_get_account_info(self, mock_post, mock_get):
        self.mock_connect(mock_post)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'accountListResponse': {
                'accounts': [{'accountId': '12345', 'value': 10000.0}]
            }
        }
        mock_get.return_value = mock_response
    
        self.broker.connect()
        account_info = self.broker.get_account_info()
        self.assertEqual(account_info, {'value': 10000.0})
        self.assertEqual(self.broker.account_id, '12345')

    @patch('brokers.etrade_broker.requests.post')
    @patch('brokers.etrade_broker.requests.get')
    def skip_test_place_order(self, mock_get, mock_post):
        self.mock_connect(mock_post)
        
        # Mock get_account_info response
        mock_get.return_value = MagicMock(json=MagicMock(return_value={
            'accountListResponse': {
                'accounts': [{'accountId': '12345', 'value': 10000.0}]
            }
        }))
        
        # Mock place_order response
        mock_post.return_value = MagicMock(json=MagicMock(return_value={'status': 'filled', 'filled_price': 155.00}))

        self.broker.connect()
        self.broker.get_account_info()
        order_info = self.broker.place_order('AAPL', 10, 'buy', 'example_strategy', 150.00)

        self.assertEqual(order_info, {'status': 'filled', 'filled_price': 155.00})

        # Verify the trade was inserted
        trade = self.session.query(Trade).filter_by(symbol='AAPL').first()
        self.assertIsNotNone(trade)

        # Verify the balance was updated
        balance = self.session.query(Balance).filter_by(broker='E*TRADE', strategy='example_strategy').first()
        self.assertIsNotNone(balance)
        self.assertEqual(balance.total_balance, 10000.0 + (10 * 155.00))  # Assuming the balance should include the executed trade

    @patch('brokers.etrade_broker.requests.get')
    @patch('brokers.etrade_broker.requests.post')
    def test_get_order_status(self, mock_post_connect, mock_get):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'completed'}
        mock_get.return_value = mock_response

        self.broker.connect()
        order_status = self.broker.get_order_status('order_id')
        self.assertEqual(order_status, {'status': 'completed'})

    @patch('brokers.etrade_broker.requests.put')
    @patch('brokers.etrade_broker.requests.post')
    def test_cancel_order(self, mock_post_connect, mock_put):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'cancelled'}
        mock_put.return_value = mock_response

        self.broker.connect()
        cancel_status = self.broker.cancel_order('order_id')
        self.assertEqual(cancel_status, {'status': 'cancelled'})

    @patch('brokers.etrade_broker.requests.get')
    @patch('brokers.etrade_broker.requests.post')
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
