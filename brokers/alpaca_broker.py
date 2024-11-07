import requests
import time
from brokers.base_broker import BaseBroker
from utils.logger import logger
import aiohttp

class AlpacaBroker(BaseBroker):
    def __init__(self, api_key, secret_key, engine, base_url="https://paper-api.alpaca.markets", **kwargs):
        super().__init__(api_key, secret_key, 'Alpaca', engine=engine, **kwargs)
        self.base_url = base_url
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key
        }
        self.account_id = None
        logger.info('Initialized AlpacaBroker', extra={'base_url': self.base_url})
        self._get_account_info()

    def connect(self):
        logger.info('Connecting to Alpaca API')
        # Connection is established via API keys; no additional connection steps required.
        pass

    def _get_account_info(self):
        logger.debug('Retrieving account information')
        try:
            response = requests.get(f"{self.base_url}/v2/account", headers=self.headers)
            response.raise_for_status()
            account_info = response.json()
            self.account_id = account_info['account_number']
            logger.info('Account info retrieved', extra={'account_id': self.account_id, 'account_status': account_info['status']})
            return account_info
        except requests.RequestException as e:
            logger.error('Failed to retrieve account information', extra={'error': str(e)})
            return None

    def get_positions(self):
        logger.info('Retrieving positions')
        try:
            response = requests.get(f"{self.base_url}/v2/positions", headers=self.headers)
            response.raise_for_status()
            positions_data = response.json()
            positions = {p['symbol']: p for p in positions_data}
            logger.info('Positions retrieved', extra={'positions': positions})
            return positions
        except requests.RequestException as e:
            logger.error('Failed to retrieve positions', extra={'error': str(e)})
            return {}

    def _place_order(self, symbol, quantity, side, price=None, order_type='limit', time_in_force='day'):
        logger.info('Placing order', extra={'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
        try:
            order_data = {
                "symbol": symbol,
                "qty": quantity,
                "side": side,
                "type": order_type,
                "time_in_force": time_in_force
            }
            if order_type == 'limit' and price is not None:
                order_data["limit_price"] = str(price)

            response = requests.post(f"{self.base_url}/v2/orders", json=order_data, headers=self.headers)
            response.raise_for_status()
            order_response = response.json()
            logger.info('Order placed', extra={'order_id': order_response.get('id')})
            return order_response
        except requests.RequestException as e:
            logger.error('Failed to place order', extra={'error': str(e)})
            return {}

    def _place_option_order(self, symbol, quantity, side, option_type, strike_price, expiration_date, price=None, order_type='limit', time_in_force='day'):
        logger.info('Placing option order', extra={'symbol': symbol, 'quantity': quantity, 'side': side, 'option_type': option_type, 'strike_price': strike_price, 'expiration_date': expiration_date, 'price': price, 'order_type': order_type})
        try:
            # Fetch the option contract details
            contracts_url = f"{self.base_url}/v2/options/contracts?underlying_symbols={symbol}&expiration_date={expiration_date}&strike_price={strike_price}&type={option_type}"
            contracts_response = requests.get(contracts_url, headers=self.headers)
            contracts_response.raise_for_status()
            contracts = contracts_response.json().get('option_contracts', [])
            if not contracts:
                logger.error('No matching option contract found', extra={'symbol': symbol, 'strike_price': strike_price, 'expiration_date': expiration_date, 'option_type': option_type})
                return {}

            option_symbol = contracts[0]['symbol']

            order_data = {
                "symbol": option_symbol,
                "qty": quantity,
                "side": side,
                "type": order_type,
                "time_in_force": time_in_force,
                "asset_class": "option"
            }
            if order_type == 'limit' and price is not None:
                order_data["limit_price"] = str(price)

            response = requests.post(f"{self.base_url}/v2/orders", json=order_data, headers=self.headers)
            response.raise_for_status()
            order_response = response.json()
            logger.info('Option order placed', extra={'order_id': order_response.get('id')})
            return order_response
        except requests.RequestException as e:
            logger.error('Failed to place option order', extra={'error': str(e)})
            return {}

    def _get_order_status(self, order_id):
        logger.info('Retrieving order status', extra={'order_id': order_id})
        try:
            response = requests.get(f"{self.base_url}/v2/orders/{order_id}", headers=self.headers)
            response.raise_for_status()
            order_status = response.json()
            logger.info('Order status retrieved', extra={'order_status': order_status})
            return order_status
        except requests.RequestException as e:
            logger.error('Failed to retrieve order status', extra={'error': str(e)})
            return None

    def _cancel_order(self, order_id):
        logger.info('Cancelling order', extra={'order_id': order_id})
        try:
            response = requests.delete(f"{self.base_url}/v2/orders/{order_id}", headers=self.headers)
            response.raise_for_status()
            logger.info('Order cancelled successfully', extra={'order_id': order_id})
            return response.json()
        except requests.RequestException as e:
            logger.error('Failed to cancel order', extra={'error': str(e)})
            return None

    async def get_current_price(self, symbol):
        logger.info('Retrieving current price', extra={'symbol': symbol})
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/v2/stocks/{symbol}/quotes/latest", headers=self.headers) as response:
                    response.raise_for_status()
                    data = await response.json()
                    last_price = data.get('last', {}).get('price')
                    logger.info('Current price retrieved', extra={'symbol': symbol, 'last_price': last_price})
                    return last_price
        except aiohttp.ClientError as e:
            logger.error('Failed to retrieve current price', extra={'error': str(e)})
            return None

    def get_bid_ask(self, symbol):
        logger.info('Retrieving bid/ask', extra={'symbol': symbol})
        try:
            response = requests.get(f"{self.base_url}/v2/stocks/{symbol}/quotes/latest", headers=self.headers)
            response.raise_for_status()
            quote = response.json()
            bid = quote.get('bid_price')
            ask = quote.get('ask_price')
            logger.info('Bid/ask retrieved', extra={'symbol': symbol, 'bid': bid, 'ask': ask})
            return {'bid': bid, 'ask': ask}
        except requests.RequestException as e:
            logger.error('Failed to retrieve bid/ask', extra={'error': str(e)})
            return {}
