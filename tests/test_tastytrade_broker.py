import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy import create_engine
from brokers.tastytrade_broker import TastytradeBroker
from database.models import Trade, Balance
from .base_test import BaseTest

class TestTastytradeBroker(BaseTest):

    def setUp(self):
        super().setUp()  # Call the setup from BaseTest

    def mock_connect(self, mock_post, mock_get, mock_prod_sesh):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'session-token': 'token',
                'user': {
                    'username': 'testuser'
                }
            }
        }
        mock_post.return_value = mock_response
        self.broker = TastytradeBroker('myusername', 'mypassword', engine=self.engine)

    @patch('brokers.tastytrade_broker.ProductionSession', autospec=True)
    @patch('brokers.tastytrade_broker.requests.get')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_connect(self, mock_post, mock_get, mock_prod_sesh):
        self.mock_connect(mock_post, mock_get, mock_prod_sesh)
        self.broker.connect()
        self.assertTrue(hasattr(self.broker, 'auth'))
        mock_prod_sesh.assert_called_with('myusername', 'mypassword')


    @patch('brokers.tastytrade_broker.ProductionSession', autospec=True)
    @patch('brokers.tastytrade_broker.requests.get')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_get_account_info(self, mock_post, mock_get, mock_prod_sesh):
        self.mock_connect(mock_post, mock_get, mock_prod_sesh)

        # Mock response for accounts
        mock_response_accounts = MagicMock()
        mock_response_accounts.json.return_value = {
            'data': {
                'items': [{'account': {'account-number': '12345'}}]
            }
        }

        # Mock response for balances
        mock_response_balances = MagicMock()
        mock_response_balances.json.return_value = {
            'data': {
                'equity-buying-power': 5000.0,
                'net-liquidating-value': 10000.0,
                'cash-balance': 2000.0,  # Add cash-balance to the mock response
            }
        }

        # Set the side effect for the mock GET requests
        mock_get.side_effect = [mock_response_accounts, mock_response_balances]

        # Assuming self.broker is already defined and initialized in the test setup
        self.broker.connect()

        # Call the method to be tested
        account_info = self.broker._get_account_info()

        # Perform assertions as needed
        self.assertEqual(self.broker.account_id, '12345')
        self.assertEqual(account_info.get('buying_power'), 5000.0)
        self.assertEqual(account_info.get('cash'), 2000.0)

    @patch('brokers.tastytrade_broker.DXLinkStreamer', new_callable=AsyncMock)
    @patch('brokers.tastytrade_broker.ProductionSession', autospec=True)
    @patch('brokers.tastytrade_broker.requests.post')
    @patch('brokers.tastytrade_broker.requests.get')
    async def test_place_order(self, mock_get, mock_post, mock_prod_sesh, mock_dx_streamer):
        self.mock_connect(mock_post, mock_get, mock_prod_sesh)
        # Update the mock response to include 'session-token'
        mock_post.side_effect = [
            MagicMock(json=MagicMock(return_value={
                'data': {
                    'session-token': 'token',
                    'user': {'username': 'testuser'}
                }
            })),
            MagicMock(json=MagicMock(return_value={
                'data': {'order': {'order_id': 'order123', 'status': 'filled', 'filled_price': 155.00}}
            }))
        ]

        # Mock get_account_info response
        mock_get.side_effect = [
            MagicMock(json=MagicMock(return_value={
                'data': {
                    'items': [{'account': {'account-number': '12345'}}]
                }
            })),
            MagicMock(json=MagicMock(return_value={
                'data': {
                    'equity-buying-power': 5000.0,
                    'net-liquidating-value': 10000.0
                }
            }))
        ]

        # Mock DXLinkStreamer response for get_current_price
        mock_dx_streamer.return_value.__aenter__.return_value.get_event.return_value = MagicMock(bidPrice=150.0, askPrice=160.0)

        self.broker.connect()
        self.broker._get_account_info()
        order_info = await self.broker._place_order('AAPL', 10, 'buy', 150.00)

        self.assertEqual(order_info, {'data': {'order': {'order_id': 'order123', 'status': 'filled', 'filled_price': 155.00}}})

        # Verify the trade was inserted
        trade = self.session.query(Trade).filter_by(symbol='AAPL').first()
        self.assertIsNotNone(trade)

        # Verify the balance was updated
        balance = self.session.query(Balance).filter_by(broker='Tastytrade', strategy='example_strategy').first()
        self.assertIsNotNone(balance)
        self.assertEqual(balance.total_balance, 10000.0 + (10 * 155.00))  # Assuming the balance should include the executed trade

    @patch('brokers.tastytrade_broker.ProductionSession', autospec=True)
    @patch('brokers.tastytrade_broker.requests.get')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_get_order_status(self, mock_post_connect, mock_get, mock_prod_sesh):
        self.mock_connect(mock_post_connect, mock_get, mock_prod_sesh)
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': {'status': 'completed'}}
        mock_get.return_value = mock_response

        self.broker.connect()
        order_status = self.broker._get_order_status('order_id')
        self.assertEqual(order_status, {'data': {'status': 'completed'}})

    @patch('brokers.tastytrade_broker.ProductionSession', autospec=True)
    @patch('brokers.tastytrade_broker.requests.get')
    @patch('brokers.tastytrade_broker.requests.put')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_cancel_order(self, mock_post_connect, mock_put, mock_get, mock_prod_sesh):
        self.mock_connect(mock_post_connect, mock_get, mock_prod_sesh)
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': {'status': 'cancelled'}}
        mock_put.return_value = mock_response

        self.broker.connect()
        cancel_status = self.broker._cancel_order('order_id')
        self.assertEqual(cancel_status, {'data': {'status': 'cancelled'}})

    @patch('brokers.tastytrade_broker.ProductionSession', autospec=True)
    @patch('brokers.tastytrade_broker.requests.get')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_get_options_chain(self, mock_post_connect, mock_get, mock_prod_sesh):
        self.mock_connect(mock_post_connect, mock_get, mock_prod_sesh)
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': {'items': 'chain'}}
        mock_get.return_value = mock_response

        self.broker.connect()
        options_chain = self.broker._get_options_chain('AAPL', '2024-12-20')
        self.assertEqual(options_chain, {'data': {'items': 'chain'}})

if __name__ == '__main__':
    unittest.main()
