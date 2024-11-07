import pytest
from unittest.mock import patch, MagicMock
from brokers.alpaca_broker import AlpacaBroker
from .base_test import BaseTest
from database.models import Balance, Trade
from sqlalchemy.sql import select

@pytest.mark.asyncio
class TestAlpacaBroker(BaseTest):

    async def asyncSetUp(self):
        await super().setUp()  # Call the setup from BaseTest
        self.broker = await AlpacaBroker('api_key', 'secret_key', engine=self.engine)

    def mock_connect(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'account_number': '12345', 'status': 'ACTIVE'}
        mock_get.return_value = mock_response

    @patch('brokers.alpaca_broker.requests.get')
    @patch('brokers.alpaca_broker.requests.post')
    async def test_connect(self, mock_post, mock_get):
        self.mock_connect(mock_get)
        await self.broker.connect()
        assert hasattr(self.broker, 'headers')

    @patch('brokers.alpaca_broker.requests.get')
    async def test_get_account_info(self, mock_get):
        self.mock_connect(mock_get)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'account_number': '12345',
            'status': 'ACTIVE',
            'cash': 10000.0,
            'buying_power': 50000.0
        }
        mock_get.return_value = mock_response

        await self.broker.connect()
        account_info = await self.broker.get_account_info()
        assert account_info == {
            'account_number': '12345',
            'status': 'ACTIVE',
            'cash': 10000.0,
            'buying_power': 50000.0
        }
        assert self.broker.account_id == '12345'

    @patch('brokers.alpaca_broker.requests.get')
    async def test_get_positions(self, mock_get):
        self.mock_connect(mock_get)
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {'symbol': 'AAPL', 'qty': 10, 'avg_entry_price': 150.00, 'market_value': 1550.00}
        ]
        mock_get.return_value = mock_response

        await self.broker.connect()
        positions = await self.broker.get_positions()
        assert positions == {'AAPL': {'symbol': 'AAPL', 'qty': 10, 'avg_entry_price': 150.00, 'market_value': 1550.00}}

    @patch('brokers.alpaca_broker.requests.post')
    async def test_place_order(self, mock_post):
        self.mock_connect(mock_post)
        mock_response = MagicMock()
        mock_response.json.return_value = {'id': 'order123', 'status': 'filled', 'filled_avg_price': 155.00}
        mock_post.return_value = mock_response

        await self.broker.connect()
        order_info = await self.broker._place_order('AAPL', 10, 'buy', price=150.00, order_type='limit')

        assert order_info == {'id': 'order123', 'status': 'filled', 'filled_avg_price': 155.00}

        # Verify the trade was inserted
        trade = await self.session.execute(select(Trade).filter_by(symbol='AAPL'))
        trade = trade.scalar_one()
        assert trade is not None

        # Verify the balance was updated
        balance = await self.session.execute(select(Balance).filter_by(broker='Alpaca', strategy='default'))
        balance = balance.scalar_one()
        assert balance is not None
        assert balance.total_balance == 10000.0 + (10 * 155.00)  # Assuming balance reflects executed trade

    @patch('brokers.alpaca_broker.requests.get')
    async def test_get_order_status(self, mock_get):
        self.mock_connect(mock_get)
        mock_response = MagicMock()
        mock_response.json.return_value = {'id': 'order123', 'status': 'completed'}
        mock_get.return_value = mock_response

        await self.broker.connect()
        order_status = await self.broker._get_order_status('order123')
        assert order_status == {'id': 'order123', 'status': 'completed'}

    @patch('brokers.alpaca_broker.requests.delete')
    async def test_cancel_order(self, mock_delete):
        self.mock_connect(mock_delete)
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'cancelled'}
        mock_delete.return_value = mock_response

        await self.broker.connect()
        cancel_status = await self.broker._cancel_order('order123')
        assert cancel_status == {'status': 'cancelled'}

    @patch('brokers.alpaca_broker.requests.get')
    async def test_get_bid_ask(self, mock_get):
        self.mock_connect(mock_get)
        mock_response = MagicMock()
        mock_response.json.return_value = {'bid_price': 149.00, 'ask_price': 151.00}
        mock_get.return_value = mock_response

        await self.broker.connect()
        bid_ask = await self.broker.get_bid_ask('AAPL')
        assert bid_ask == {'bid': 149.00, 'ask': 151.00}

    @patch('brokers.alpaca_broker.requests.get')
    async def test_place_option_order(self, mock_get):
        self.mock_connect(mock_get)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'option_contracts': [{'symbol': 'AAPL220819C00150000'}]
        }
        mock_get.return_value = mock_response

        @patch('brokers.alpaca_broker.requests.post')
        async def place_option_order_test(mock_post):
            mock_order_response = MagicMock()
            mock_order_response.json.return_value = {'id': 'option_order123', 'status': 'filled'}
            mock_post.return_value = mock_order_response

            await self.broker.connect()
            order_info = await self.broker._place_option_order('AAPL', 1, 'buy', 'call', 150.00, '2024-12-20', price=10.00)
            assert order_info == {'id': 'option_order123', 'status': 'filled'}
