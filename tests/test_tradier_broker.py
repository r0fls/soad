import pytest
from unittest.mock import patch, MagicMock
from brokers.tradier_broker import TradierBroker
from .base_test import BaseTest
from database.models import Balance, Trade
from sqlalchemy.sql import select

@pytest.mark.asyncio
class TestTradierBroker(BaseTest):

    async def asyncSetUp(self):
        await super().setUp()  # Call the setup from BaseTest
        self.broker = await TradierBroker('api_key', 'secret_key', engine=self.engine)

    def mock_connect(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'profile': {'account': {'account_number': '12345', 'balance': 10000.0}}}
        mock_post.return_value = mock_response

    @patch('brokers.tradier_broker.requests.get')
    @patch('brokers.tradier_broker.requests.post')
    async def test_connect(self, mock_post, mock_get):
        self.mock_connect(mock_post)
        await self.broker.connect()
        assert hasattr(self.broker, 'headers')

    @patch('brokers.tradier_broker.requests.get')
    @patch('brokers.tradier_broker.requests.post')
    async def test_get_account_info(self, mock_post, mock_get):
        self.mock_connect(mock_post)
        mock_response = MagicMock()
        mock_response.json.return_value = {'profile': {'account': {'account_number': '12345', 'balance': 10000.0}}}
        mock_get.return_value = mock_response

        await self.broker.connect()
        account_info = await self.broker.get_account_info()
        assert account_info == {'value': 10000.0}
        assert self.broker.account_id == '12345'

    @patch('brokers.tradier.requests.post')
    @patch('brokers.tradier.requests.get')
    async def test_place_order(self, mock_get, mock_post):
        self.mock_connect(mock_post)
        mock_response = MagicMock()
        mock_response.json.return_value = {'profile': {'account': {'account_number': '12345', 'balance': 10000.0}}}
        mock_get.return_value = mock_response

        # Mock place_order response
        mock_post.return_value = MagicMock(json=MagicMock(return_value={'status': 'filled', 'filled_price': 155.00}))

        await self.broker.connect()
        await self.broker.get_account_info()
        order_info = await self.broker.place_order('AAPL', 10, 'buy', 'example_strategy', 150.00)

        assert order_info == {'status': 'filled', 'filled_price': 155.00}

        # Verify the trade was inserted
        trade = await self.session.execute(select(Trade).filter_by(symbol='AAPL'))
        trade = trade.scalar_one()
        assert trade is not None

        # Verify the balance was updated
        balance = await self.session.execute(select(Balance).filter_by(broker='E*TRADE', strategy='example_strategy'))
        balance = balance.scalar_one()
        assert balance is not None
        assert balance.total_balance == 10000.0 + (10 * 155.00)  # Assuming the balance should include the executed trade

    @patch('brokers.tradier_broker.requests.get')
    @patch('brokers.tradier_broker.requests.post')
    async def test_get_order_status(self, mock_post_connect, mock_get):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'completed'}
        mock_get.return_value = mock_response

        await self.broker.connect()
        order_status = await self.broker.get_order_status('order_id')
        assert order_status == {'status': 'completed'}

    @patch('brokers.tradier_broker.requests.delete')
    @patch('brokers.tradier_broker.requests.post')
    async def test_cancel_order(self, mock_post_connect, mock_delete):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'cancelled'}
        mock_delete.return_value = mock_response

        await self.broker.connect()
        cancel_status = await self.broker.cancel_order('order_id')
        assert cancel_status == {'status': 'cancelled'}

    @patch('brokers.tradier_broker.requests.get')
    @patch('brokers.tradier_broker.requests.post')
    async def test_get_options_chain(self, mock_post_connect, mock_get):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {'options': 'chain'}
        mock_get.return_value = mock_response

        await self.broker.connect()
        options_chain = await self.broker.get_options_chain('AAPL', '2024-12-20')
        assert options_chain == {'options': 'chain'}
