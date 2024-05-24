import requests
from requests_oauthlib import OAuth1
from brokers.base_broker import BaseBroker

class EtradeBroker(BaseBroker):
    BASE_URL = 'https://api.etrade.com/v1'

    def __init__(self, api_key, secret_key):
        super().__init__(api_key, secret_key, 'E*TRADE')
        self.account_id = None

    def connect(self):
        self.auth = OAuth1(self.api_key, self.secret_key)

    def _get_account_info(self):
        url = f'{self.BASE_URL}/accounts/list'
        response = requests.get(url, auth=self.auth)
        account_info = response.json()
        self.account_id = account_info['accountListResponse']['accounts'][0]['accountId']
        return account_info

    def _place_order(self, symbol, quantity, order_type, price=None):
        url = f'{self.BASE_URL}/accounts/{self.account_id}/orders/place'
        order = {
            'symbol': symbol,
            'quantity': quantity,
            'price': price,
            'orderType': 'MARKET' if price is None else 'LIMIT',
            'action': order_type.upper()
        }
        response = requests.post(url, auth=self.auth, json=order)
        return response.json()

    def _get_order_status(self, order_id):
        url = f'{self.BASE_URL}/accounts/{self.account_id}/orders/{order_id}'
        response = requests.get(url, auth=self.auth)
        return response.json()

    def _cancel_order(self, order_id):
        url = f'{self.BASE_URL}/accounts/{self.account_id}/orders/cancel'
        response = requests.put(url, auth=self.auth, json={'orderId': order_id})
        return response.json()

    def _get_options_chain(self, symbol, expiration_date):
        url = f'{self.BASE_URL}/market/options/search'
        params = {
            'symbol': symbol,
            'expiryYear': expiration_date.split('-')[0],
            'expiryMonth': expiration_date.split('-')[1],
            'expiryDay': expiration_date.split('-')[2]
        }
        response = requests.get(url, auth=self.auth, params=params)
        return response.json()
