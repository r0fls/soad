import requests
from brokers.base_broker import BaseBroker

class TradierBroker(BaseBroker):
    BASE_URL = 'https://api.tradier.com/v1'

    def __init__(self, api_key, secret_key):
        super().__init__(api_key, secret_key, 'Tradier')
        self.account_id = None

    def connect(self):
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        }

    def _get_account_info(self):
        url = f'{self.BASE_URL}/user/profile'
        response = requests.get(url, headers=self.headers)
        account_info = response.json()

        # Assuming the response contains account information with an account ID
        self.account_id = account_info['profile']['account']['account_number']
        return account_info

    def _place_order(self, symbol, quantity, order_type, price=None):
        url = f'{self.BASE_URL}/accounts/{self.account_id}/orders'
        order = {
            'class': 'equity',
            'symbol': symbol,
            'side': order_type,
            'quantity': quantity,
            'type': 'market' if price is None else 'limit',
            'price': price
        }
        response = requests.post(url, headers=self.headers, data=order)
        return response.json()

    def _get_order_status(self, order_id):
        url = f'{self.BASE_URL}/accounts/{self.account_id}/orders/{order_id}'
        response = requests.get(url, headers=self.headers)
        return response.json()

    def _cancel_order(self, order_id):
        url = f'{self.BASE_URL}/accounts/{self.account_id}/orders/{order_id}'
        response = requests.delete(url, headers=self.headers)
        return response.json()

    def _get_options_chain(self, symbol, expiration_date):
        url = f'{self.BASE_URL}/markets/options/chains'
        params = {
            'symbol': symbol,
            'expiration': expiration_date
        }
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()
