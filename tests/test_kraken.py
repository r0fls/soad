import pytest
from unittest.mock import patch, MagicMock
from brokers.kraken_broker import KrakenBroker
from .base_test import BaseTest
from database.models import Balance, Trade
from sqlalchemy.sql import select

@pytest.fixture
def kraken_broker():
    api_key = 'testapikey'
    secret_key = 'dGVzdHNlY3JldGtleQ=='
    engine = MagicMock()  # Mock the engine
    return KrakenBroker(api_key=api_key, secret_key=secret_key, engine=engine)


# TODO: use pytest
@pytest.mark.asyncio
class TestKrakenBroker(BaseTest):

    async def asyncSetUp(self):
        await super().setUp()
        self.broker = await KrakenBroker('api_key', 'secret_key', engine=self.engine)

    def mock_connect(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'result': {'ZUSD': '10000.0000'}}
        mock_post.return_value = mock_response

    @patch('brokers.kraken_broker.requests.post')
    async def test_connect(self, mock_post):
        self.mock_connect(mock_post)
        await self.broker.connect()
        assert hasattr(self.broker, 'api_key')
        assert hasattr(self.broker, 'secret_key')

    @patch('brokers.kraken_broker.requests.post')
    async def test_get_account_info(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'result': {
                'ZUSD': '10000.0000',
                'XXBT': '1.0000'
            }
        }
        mock_post.return_value = mock_response

        await self.broker.connect()
        account_info = await self.broker._get_account_info()
        assert account_info == {
            'ZUSD': '10000.0000',
            'XXBT': '1.0000'
        }
        assert self.broker.account_id is not None

    @patch('brokers.kraken_broker.requests.post')
    async def test_get_positions(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'result': {
                'TXID1': {
                    'pair': 'XXBTZUSD',
                    'type': 'buy',
                    'volume': '1.0000'
                }
            }
        }
        mock_post.return_value = mock_response

        await self.broker.connect()
        positions = await self.broker.get_positions()
        assert positions == {
            'XXBTZUSD': {
                'pair': 'XXBTZUSD',
                'type': 'buy',
                'volume': '1.0000'
            }
        }

    @patch('brokers.kraken_broker.requests.post')
    async def test_place_order(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'result': {
                'txid': ['TXID1'],
                'descr': {
                    'order': 'buy 1.00000000 XBTUSD @ limit 50000.0'
                }
            }
        }
        mock_post.return_value = mock_response

        await self.broker.connect()
        order_info = await self.broker._place_order('XBTUSD', 1.0, 'buy', price=50000.0)

        assert order_info == {
            'txid': ['TXID1'],
            'descr': {
                'order': 'buy 1.00000000 XBTUSD @ limit 50000.0'
            }
        }

        # Verify the trade was inserted
        trade = await self.session.execute(select(Trade).filter_by(symbol='XBTUSD'))
        trade = trade.scalar_one()
        assert trade is not None

        # Verify the balance was updated
        balance = await self.session.execute(select(Balance).filter_by(broker='Kraken', strategy='default'))
        balance = balance.scalar_one()
        assert balance is not None

    @patch('brokers.kraken_broker.requests.post')
    async def test_get_order_status(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'result': {
                'TXID1': {
                    'status': 'closed',
                    'vol_exec': '1.00000000',
                    'price': '50000.0'
                }
            }
        }
        mock_post.return_value = mock_response

        await self.broker.connect()
        order_status = await self.broker._get_order_status('TXID1')
        assert order_status == {
            'status': 'closed',
            'vol_exec': '1.00000000',
            'price': '50000.0'
        }

    @patch('brokers.kraken_broker.requests.post')
    async def test_cancel_order(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'result': {
                'count': 1
            }
        }
        mock_post.return_value = mock_response

        await self.broker.connect()
        cancel_status = await self.broker._cancel_order('TXID1')
        assert cancel_status == {'count': 1}

    @patch('brokers.kraken_broker.requests.get')
    async def test_get_bid_ask(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'result': {
                'XXBTZUSD': {
                    'b': ['49900.0', '1', '1.0'],
                    'a': ['50000.0', '1', '1.0']
                }
            }
        }
        mock_get.return_value = mock_response

        await self.broker.connect()
        bid_ask = await self.broker.get_bid_ask('XXBTZUSD')
        assert bid_ask == {'bid': 49900.0, 'ask': 50000.0}

    @patch('aiohttp.ClientSession.get')
    async def test_get_current_price(self, mock_get):
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            'result': {
                'XXBTZUSD': {
                    'c': ['50000.0', '1.00000000']
                }
            }
        })
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value.__aenter__.return_value = mock_response

        await self.broker.connect()
        current_price = await self.broker.get_current_price('XXBTZUSD')
        assert current_price == 50000.0

@patch('brokers.kraken_broker.KrakenBroker._make_request')
def skip_test_get_account_info_usd_balance(mock_make_request, kraken_broker):
    # Mock response for USD balance
    mock_make_request.return_value = {
        'result': {
            'ZUSD': '1000.00'
        }
    }

    result = kraken_broker._get_account_info()
    assert result is not None
    assert result['total_value_usd'] == 1000.0
    assert result['balances']['ZUSD'] == '1000.00'
