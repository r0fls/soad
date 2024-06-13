import requests
import time
from brokers.base_broker import BaseBroker
from utils.logger import logger  # Import the logger

class TastytradeBroker(BaseBroker):
    def __init__(self, username, password, engine, **kwargs):
        super().__init__(username, password, 'Tastytrade', engine=engine, **kwargs)
        self.base_url = 'https://api.tastytrade.com'
        self.username = username
        self.password = password
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self.order_timeout = 1
        self.auto_cancel_orders = True
        logger.info('Initialized TastytradeBroker', extra={'base_url': self.base_url})
        self.connect()

    def connect(self):
        logger.info('Connecting to Tastytrade API')
        auth_data = {
            "login": self.username,
            "password": self.password,
            "remember-me": True
        }
        response = requests.post(f"{self.base_url}/sessions", json=auth_data, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        auth_response = response.json().get('data')
        self.auth = auth_response['session-token']
        self.headers["Authorization"] = self.auth
        logger.info('Connected to Tastytrade API')

    def _get_account_info(self):
        logger.info('Retrieving account information')
        try:
            response = requests.get(f"{self.base_url}/customers/me/accounts", headers=self.headers)
            response.raise_for_status()
            account_info = response.json()
            account_id = account_info['data']['items'][0]['account']['account-number']
            self.account_id = account_id
            logger.info('Account info retrieved', extra={'account_id': self.account_id})

            response = requests.get(f"{self.base_url}/accounts/{self.account_id}/balances", headers=self.headers)
            response.raise_for_status()
            account_data = response.json().get('data')

            if not account_data:
                logger.error("Invalid account info response")

            buying_power = account_data['equity-buying-power']
            account_value = account_data['net-liquidating-value']
            # TODO: margin/cash does this matter here?
            account_type = None

            logger.info('Account balances retrieved', extra={'account_type': account_type, 'buying_power': buying_power, 'value': account_value})
            return {
                'account_number': self.account_id,
                'account_type': account_type,
                'buying_power': float(buying_power),
                'value': float(account_value)
            }
        except requests.RequestException as e:
            logger.error('Failed to retrieve account information', extra={'error': str(e)})

    def get_positions(self):
        logger.info('Retrieving positions')
        url = f"{self.base_url}/accounts/{self.account_id}/positions"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            positions_data = response.json()['data']['items']

            positions = {p['symbol']: p for p in positions_data}
            logger.info('Positions retrieved', extra={'positions': positions})
            return positions
        except requests.RequestException as e:
            logger.error('Failed to retrieve positions', extra={'error': str(e)})

    def _place_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        try:
            quote_url = f"{self.base_url}/markets/quotes/{symbol}"
            quote_response = requests.get(quote_url, headers=self.headers)
            quote_response.raise_for_status()
            quote = quote_response.json()['data']['items'][0]
            bid = quote['bid']
            ask = quote['ask']

            if price is None:
                price = round((bid + ask) / 2, 2)

            order_data = {
                "class": "equity",
                "symbol": symbol,
                "quantity": quantity,
                "side": order_type,
                "type": "limit",
                "duration": "day",
                "price": price
            }

            response = requests.post(f"{self.base_url}/accounts/{self.account_id}/orders", json=order_data, headers=self.headers)
            response.raise_for_status()

            order_id = response.json()['data']['order']['order_id']
            logger.info('Order placed', extra={'order_id': order_id})

            if self.auto_cancel_orders:
                time.sleep(self.order_timeout)
                order_status_url = f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}"
                status_response = requests.get(order_status_url, headers=self.headers)
                status_response.raise_for_status()
                order_status = status_response.json()['data']['order']['status']

                if order_status != 'filled':
                    cancel_url = f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}/cancel"
                    cancel_response = requests.put(cancel_url, headers=self.headers)
                    cancel_response.raise_for_status()
                    logger.info('Order cancelled', extra={'order_id': order_id})

            data = response.json()
            if data.get('filled_price') is None:
                data['filled_price'] = price
            logger.info('Order execution complete', extra={'order_data': data})
            return data
        except requests.RequestException as e:
            logger.error('Failed to place order', extra={'error': str(e)})

    def _get_order_status(self, order_id):
        logger.info('Retrieving order status', extra={'order_id': order_id})
        try:
            response = requests.get(f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}", headers=self.headers)
            response.raise_for_status()
            order_status = response.json()
            logger.info('Order status retrieved', extra={'order_status': order_status})
            return order_status
        except requests.RequestException as e:
            logger.error('Failed to retrieve order status', extra={'error': str(e)})

    def _cancel_order(self, order_id):
        logger.info('Cancelling order', extra={'order_id': order_id})
        try:
            response = requests.put(f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}/cancel", headers=self.headers)
            response.raise_for_status()
            cancellation_response = response.json()
            logger.info('Order cancelled successfully', extra={'cancellation_response': cancellation_response})
            return cancellation_response
        except requests.RequestException as e:
            logger.error('Failed to cancel order', extra={'error': str(e)})

    def _get_options_chain(self, symbol, expiration_date):
        logger.info('Retrieving options chain', extra={'symbol': symbol, 'expiration_date': expiration_date})
        try:
            response = requests.get(f"{self.base_url}/markets/options/chains?symbol={symbol}&expiration={expiration_date}", headers=self.headers)
            response.raise_for_status()
            options_chain = response.json()
            logger.info('Options chain retrieved', extra={'options_chain': options_chain})
            return options_chain
        except requests.RequestException as e:
            logger.error('Failed to retrieve options chain', extra={'error': str(e)})

    # TODO: fix
    def get_current_price(self, symbol):
        logger.info('Retrieving current price', extra={'symbol': symbol})
        try:
            response = requests.get(f"{self.base_url}/market-data/quotes", params={"symbols": symbol}, headers=self.headers)
            response.raise_for_status()
            last_price = response.json()['data']['items'][0]['last']
            logger.info('Current price retrieved', extra={'symbol': symbol, 'last_price': last_price})
            return last_price
        except requests.RequestException as e:
            logger.error('Failed to retrieve current price', extra={'error': str(e)})
