import requests
from brokers.base_broker import BaseBroker

class TastytradeBroker(BaseBroker):
    BASE_URL = 'https://api.tastyworks.com'

    def __init__(self, api_key, secret_key):
        super().__init__(api_key, secret_key, 'Tastytrade')
        self.account_id = None

    def connect(self):
        login_url = f'{self.BASE_URL}/sessions'
        login_payload = {
            'login': self.api_key,
            'password': self.secret_key
        }
        response = requests.post(login_url, json=login_payload)
        if response.status_code != 200:
            print(f"Failed to connect: {response.status_code}")
            response.raise_for_status()
        response_json = response.json()
        if 'data' not in response_json or 'session-token' not in response_json['data']:
            print("Invalid response format", response_json)
            raise ValueError("Invalid response format")
        self.session_token = response_json['data']['session-token']
        self.headers = {
            'Authorization': f'Bearer {self.session_token}',
            'Accept': 'application/json'
        }

    def _get_account_info(self):
        url = f'{self.BASE_URL}/accounts'
        response = requests.get(url, headers=self.headers)
        account_info = response.json()
        self.account_id = account_info['data']['items'][0]['account']['account_number']
        return account_info

    def _place_order(self, symbol, quantity, order_type, price=None):
        url = f'{self.BASE_URL}/accounts/{self.account_id}/orders'
        order = {
            'symbol': symbol,
            'quantity': quantity,
            'price': price,
            'type': 'market' if price is None else 'limit',
            'action': order_type
        }
        response = requests.post(url, headers=self.headers, json=order)
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
        url = f'{self.BASE_URL}/markets/option-chains'
        params = {
            'symbol': symbol,
            'expiration': expiration_date
        }
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()
