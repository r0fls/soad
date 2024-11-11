import requests
import time
import hmac
import base64
import hashlib
import urllib.parse
from brokers.base_broker import BaseBroker
from utils.logger import logger
import aiohttp

class KrakenBroker(BaseBroker):
    def __init__(self, api_key, secret_key, engine, base_url="https://api.kraken.com", base_currency="ZUSD", **kwargs):
        super().__init__(api_key, secret_key, 'Kraken', engine=engine, **kwargs)
        self.base_currency = base_currency
        self.secret_key = secret_key
        self.base_url = base_url
        self.api_version = '/0'
        self.account_id = None
        logger.info('Initialized KrakenBroker', extra={'base_url': self.base_url})
        self._get_account_info()

    def _get_signature(self, urlpath, data):
        post_data = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + post_data).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()

        signature = hmac.new(base64.b64decode(self.secret_key),
                           message,
                           hashlib.sha512)
        return base64.b64encode(signature.digest()).decode()

    def _make_request(self, endpoint, data=None, method='POST'):
        if data is None:
            data = {}

        if method == 'POST':
            data['nonce'] = int(time.time() * 1000)

        headers = {
            'API-Key': self.api_key,
            'API-Sign': self._get_signature(self.api_version + endpoint, data)
        }

        url = self.base_url + self.api_version + endpoint

        try:
            if method == 'POST':
                response = requests.post(url, headers=headers, data=data)
            else:
                response = requests.get(url, headers=headers, params=data)

            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f'Request failed: {str(e)}')
            return None

    def connect(self):
        logger.info('Connecting to Kraken API')
        # Connection is established via API keys; no additional connection steps required
        pass


    def _get_account_info(self):
        """
        Calculate the total account value in USD by converting each asset balance
        using the latest market data from Kraken.
        """
        logger.debug('Retrieving account information')
        try:
            response = self._make_request('/private/Balance')
            if response and 'result' in response:
                self.account_id = self.api_key[:8]  # Using first 8 chars of API key as account ID
                logger.info('Account info retrieved', extra={'account_id': self.account_id})

                # Calculate total USD value
                account_data = response['result']
                total_value_usd = 0.0

                for asset, balance in account_data.items():
                    balance = float(balance)
                    if balance <= 0:
                        continue

                    # Handle base currency directly
                    if asset == self.base_currency:
                        total_value_usd += balance
                        continue

                    # Adjust asset symbol if necessary
                    if asset == 'BTC':
                        asset = 'XXBT'  # Convert BTC to XXBT for Kraken pair formatting

                    # Get conversion rate for the asset to base currency
                    pair = f"{asset}{self.base_currency}"
                    ticker_info = self._make_request('/public/Ticker', {'pair': pair})

                    if ticker_info and 'result' in ticker_info:
                        # Handle potential formatting issues with pairs
                        pair_key = next(iter(ticker_info['result']))
                        ask_price = float(ticker_info['result'][pair_key]['a'][0])  # Get ask price
                        total_value_usd += balance * ask_price
                        logger.debug(f'Converted {asset} balance to USD: {balance} * {ask_price} = {balance * ask_price}')
                    else:
                        logger.warning(f'No market data for {asset}. Skipping conversion.')

                logger.info('Total account value calculated', extra={'total_value_usd': total_value_usd})
                return {
                    'account_id': self.account_id,
                    'total_value_usd': total_value_usd,
                    'balances': account_data
                }
            return None

        except Exception as e:
            logger.error('Failed to retrieve account information', extra={'error': str(e)})
            return None

    def get_positions(self):
        logger.info('Retrieving positions')
        try:
            response = self._make_request('/private/OpenPositions')
            if response and 'result' in response:
                positions = {pos['pair']: pos for pos in response['result'].values()}
                logger.info('Positions retrieved', extra={'positions': positions})
                return positions
            return {}
        except Exception as e:
            logger.error('Failed to retrieve positions', extra={'error': str(e)})
            return {}

    def _place_order(self, symbol, quantity, side, price=None, order_type='limit', time_in_force='day'):
        logger.info('Placing order', extra={
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'price': price,
            'order_type': order_type
        })

        try:
            data = {
                'pair': symbol,
                'type': 'buy' if side.lower() == 'buy' else 'sell',
                'ordertype': order_type,
                'volume': str(quantity),
            }

            if order_type == 'limit' and price is not None:
                data['price'] = str(price)

            response = self._make_request('/private/AddOrder', data=data)
            if response and 'result' in response:
                order_id = response['result']['txid'][0]
                logger.info('Order placed', extra={'order_id': order_id})
                return response['result']
            return {}
        except Exception as e:
            logger.error('Failed to place order', extra={'error': str(e)})
            return {}

    def _get_order_status(self, order_id):
        logger.info('Retrieving order status', extra={'order_id': order_id})
        try:
            response = self._make_request('/private/QueryOrders', {'txid': order_id})
            if response and 'result' in response:
                order_status = response['result'][order_id]
                logger.info('Order status retrieved', extra={'order_status': order_status})
                return order_status
            return None
        except Exception as e:
            logger.error('Failed to retrieve order status', extra={'error': str(e)})
            return None

    def _cancel_order(self, order_id):
        logger.info('Cancelling order', extra={'order_id': order_id})
        try:
            response = self._make_request('/private/CancelOrder', {'txid': order_id})
            if response and 'result' in response:
                logger.info('Order cancelled successfully', extra={'order_id': order_id})
                return response['result']
            return None
        except Exception as e:
            logger.error('Failed to cancel order', extra={'error': str(e)})
            return None

    async def get_current_price(self, symbol):
        logger.info('Retrieving current price', extra={'symbol': symbol})
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}{self.api_version}/public/Ticker"
                async with session.get(url, params={'pair': symbol}) as response:
                    response.raise_for_status()
                    data = await response.json()
                    if 'result' in data and symbol in data['result']:
                        last_price = float(data['result'][symbol]['c'][0])
                        logger.info('Current price retrieved', extra={
                            'symbol': symbol,
                            'last_price': last_price
                        })
                        return last_price
                    return None
        except aiohttp.ClientError as e:
            logger.error('Failed to retrieve current price', extra={'error': str(e)})
            return None

    def get_bid_ask(self, symbol):
        logger.info('Retrieving bid/ask', extra={'symbol': symbol})
        try:
            response = requests.get(f"{self.base_url}{self.api_version}/public/Ticker", params={'pair': symbol})
            response.raise_for_status()
            data = response.json()
            if 'result' in data and symbol in data['result']:
                ticker = data['result'][symbol]
                bid = float(ticker['b'][0])
                ask = float(ticker['a'][0])
                logger.info('Bid/ask retrieved', extra={'symbol': symbol, 'bid': bid, 'ask': ask})
                return {'bid': bid, 'ask': ask}
            return {}
        except requests.RequestException as e:
            logger.error('Failed to retrieve bid/ask', extra={'error': str(e)})
            return {}
