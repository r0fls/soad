import requests
import time
from brokers.base_broker import BaseBroker
from utils.logger import logger  # Import the logger

class WebullBroker(BaseBroker):
    def __init__(self, api_key, secret_key, engine, **kwargs):
        super().__init__(api_key, secret_key, 'Webull', engine=engine, **kwargs)
        self.base_url = 'https://api.webull.com'
        self.headers = {
            "app_key": self.api_key,
            "app_secret": self.secret_key,
            "Content-Type": "application/json"
        }
        self.order_timeout = 1
        self.auto_cancel_orders = True
        logger.info('Initialized WebullBroker', extra={'base_url': self.base_url})

    def connect(self):
        logger.info('Connecting to Webull API')
        # Placeholder for actual connection logic
        pass

    def _get_account_info(self):
        logger.info('Retrieving account information')
        try:
            response = requests.get(f"{self.base_url}/v1/accounts", headers=self.headers)
            response.raise_for_status()
            account_info = response.json()
            account_id = account_info['accounts'][0]['accountId']
            self.account_id = account_id
            logger.info('Account info retrieved', extra={'account_id': self.account_id})

            url = f'{self.base_url}/v1/accounts/{self.account_id}/balances'
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            account_info = response.json()

            if not account_info:
                logger.error("Invalid account info response")

            self.account_type = account_info.get('accountType')
            buying_power = account_info.get('buyingPower')
            account_value = account_info.get('netAccountValue')
            cash = account_info.get('cashBalance')

            logger.info('Account balances retrieved', extra={'account_type': self.account_type, 'buying_power': buying_power, 'value': account_value})
            return {
                'account_number': self.account_id,
                'account_type': self.account_type,
                'buying_power': buying_power,
                'cash': cash,
                'value': account_value
            }
        except requests.RequestException as e:
            logger.error('Failed to retrieve account information', extra={'error': str(e)})

    def get_positions(self):
        logger.info('Retrieving positions')
        url = f"{self.base_url}/v1/accounts/{self.account_id}/positions"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            positions_data = response.json()['positions']

            positions = {p['ticker']['symbol']: p for p in positions_data}
            logger.info('Positions retrieved', extra={'positions': positions})
            return positions
        except requests.RequestException as e:
            logger.error('Failed to retrieve positions', extra={'error': str(e)})

    def _place_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        try:
            if price is None:
                quote_url = f"{self.base_url}/v1/market/quotes?tickers={symbol}"
                quote_response = requests.get(quote_url, headers=self.headers)
                quote_response.raise_for_status()
                quote = quote_response.json()['data'][0]
                bid = quote['bidPrice']
                ask = quote['askPrice']
                price = round((bid + ask) / 2, 2)

            order_data = {
                "tickerId": symbol,
                "action": order_type.upper(),
                "orderType": "LMT",
                "timeInForce": "DAY",
                "quantity": quantity,
                "lmtPrice": price
            }

            response = requests.post(f"{self.base_url}/v1/accounts/{self.account_id}/orders", json=order_data, headers=self.headers)
            response.raise_for_status()

            order_id = response.json()['orderId']
            logger.info('Order placed', extra={'order_id': order_id})

            if self.auto_cancel_orders:
                time.sleep(self.order_timeout)
                order_status_url = f"{self.base_url}/v1/accounts/{self.account_id}/orders/{order_id}"
                status_response = requests.get(order_status_url, headers=self.headers)
                status_response.raise_for_status()
                order_status = status_response.json()['status']

                if order_status != 'Filled':
                    try:
                        cancel_url = f"{self.base_url}/v1/accounts/{self.account_id}/orders/{order_id}/cancel"
                        cancel_response = requests.post(cancel_url, headers=self.headers)
                        cancel_response.raise_for_status()
                        logger.info('Order cancelled', extra={'order_id': order_id})
                    except requests.RequestException as e:
                        logger.error('Failed to cancel order', extra={'order_id': order_id})

            data = response.json()
            if data.get('filledPrice') is None:
                data['filledPrice'] = price
            logger.info('Order execution complete', extra={'order_data': data})
            return data
        except requests.RequestException as e:
            logger.error('Failed to place order', extra={'error': str(e)})

    def _place_option_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing option order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        try:
            if price is None:
                quote_url = f"{self.base_url}/v1/market/quotes/options?tickers={symbol}"
                quote_response = requests.get(quote_url, headers=self.headers)
                quote_response.raise_for_status()
                quote = quote_response.json()['data'][0]
                bid = quote['bidPrice']
                ask = quote['askPrice']
                price = round((bid + ask) / 2, 2)

            order_data = {
                "tickerId": symbol,
                "action": order_type.upper(),
                "orderType": "LMT",
                "timeInForce": "DAY",
                "quantity": quantity,
                "lmtPrice": price
            }

            response = requests.post(f"{self.base_url}/v1/accounts/{self.account_id}/orders", json=order_data, headers=self.headers)
            response.raise_for_status()

            order_id = response.json()['orderId']
            logger.info('Order placed', extra={'order_id': order_id})

            if self.auto_cancel_orders:
                time.sleep(self.order_timeout)
                order_status_url = f"{self.base_url}/v1/accounts/{self.account_id}/orders/{order_id}"
                status_response = requests.get(order_status_url, headers=self.headers)
                status_response.raise_for_status()
                order_status = status_response.json()['status']

                if order_status != 'Filled':
                    try:
                        cancel_url = f"{self.base_url}/v1/accounts/{self.account_id}/orders/{order_id}/cancel"
                        cancel_response = requests.post(cancel_url, headers=self.headers)
                        cancel_response.raise_for_status()
                        logger.info('Order cancelled', extra={'order_id': order_id})
                    except requests.RequestException as e:
                        logger.error('Failed to cancel order', extra={'order_id': order_id})

            data = response.json()
            if data.get('filledPrice') is None:
                data['filledPrice'] = price
            logger.info('Order execution complete', extra={'order_data': data})
            return data
        except requests.RequestException as e:
            logger.error('Failed to place order', extra={'error': str(e)})

    def _get_order_status(self, order_id):
        logger.info('Retrieving order status', extra={'order_id': order_id})
        try:
            response = requests.get(f"{self.base_url}/v1/accounts/{self.account_id}/orders/{order_id}", headers=self.headers)
            response.raise_for_status()
            order_status = response.json()
            logger.info('Order status retrieved', extra={'order_status': order_status})
            return order_status
        except requests.RequestException as e:
            logger.error('Failed to retrieve order status', extra={'error': str(e)})

    def _cancel_order(self, order_id):
        logger.info('Cancelling order', extra={'order_id': order_id})
        try:
            response = requests.delete(f"{self.base_url}/v1/accounts/{self.account_id}/orders/{order_id}", headers=self.headers)
            response.raise_for_status()
            cancellation_response = response.json()
            logger.info('Order cancelled successfully', extra={'cancellation_response': cancellation_response})
            return cancellation_response
        except requests.RequestException as e:
            logger.error('Failed to cancel order', extra={'error': str(e)})

    def _get_options_chain(self, symbol, expiration_date):
        logger.info('Retrieving options chain', extra={'symbol': symbol, 'expiration_date': expiration_date})
        try:
            response = requests.get(f"{self.base_url}/v1/market/options/chains?symbol={symbol}&expiration={expiration_date}", headers=self.headers)
            response.raise_for_status()
            options_chain = response.json()
            logger.info('Options chain retrieved', extra={'options_chain': options_chain})
            return options_chain
        except requests.RequestException as e:
            logger.error('Failed to retrieve options chain', extra={'error': str(e)})

    def get_current_price(self, symbol):
        logger.info('Retrieving current price', extra={'symbol': symbol})
        try:
            response = requests.get(f"{self.base_url}/v1/market/quotes?tickers={symbol}", headers=self.headers)
            response.raise_for_status()
            last_price = response.json().get('data')[0].get('lastPrice')
            logger.info('Current price retrieved', extra={'symbol': symbol, 'last_price': last_price})
            return last_price
        except requests.RequestException as e:
            logger.error('Failed to retrieve current price', extra={'error': str(e)})
