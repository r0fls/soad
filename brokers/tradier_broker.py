import requests
from brokers.base_broker import BaseBroker

class TradierBroker(BaseBroker):
    def __init__(self, api_key, secret_key, engine):
        super().__init__(api_key, secret_key, 'Tradier', engine)
        self.base_url = 'https://api.tradier.com/v1'

    def connect(self):
        # Implement the connection logic
        self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
        }


    def _get_account_info(self):
        # Implement account information retrieval
        response = requests.get("https://api.tradier.com/v1/user/profile", headers=self.headers)
        if response.status_code == 401:
            raise ValueError("It seems we are having trouble authenticating to Tradier")
        account_info = response.json()
        account_id = account_info['profile']['account']['account_number']
        self.account_id = account_id
        account_data = account_info.get('profile').get('account')
        return {'value': account_data.get('balance')}

    def get_positions(self):
        url = f"{self.base_url}/accounts/{self.account_id}/positions"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            positions_data = response.json()['positions']['position']
            # Singular dict response
            if type(positions_data) != list:
                positions_data = [positions_data]
            positions = {p['symbol']: p for p in positions_data}
            return positions
        else:
            response.raise_for_status()

    def _place_order(self, symbol, quantity, order_type, price=None):
        # Implement order placement
        order_data = {
            "class": "equity",
            "symbol": symbol,
            "quantity": quantity,
            "side": order_type,
            "type": "market" if price is None else "limit",
            "price": price
        }
        response = requests.post("https://api.tradier.com/v1/accounts/orders", json=order_data, headers=self.headers)
        return response.json()

    def _get_order_status(self, order_id):
        # Implement order status retrieval
        response = requests.get(f"https://api.tradier.com/v1/accounts/orders/{order_id}", headers=self.headers)
        return response.json()

    def _cancel_order(self, order_id):
        # Implement order cancellation
        response = requests.delete(f"https://api.tradier.com/v1/accounts/orders/{order_id}", headers=self.headers)
        return response.json()

    def _get_options_chain(self, symbol, expiration_date):
        # Implement options chain retrieval
        response = requests.get(f"https://api.tradier.com/v1/markets/options/chains?symbol={symbol}&expiration={expiration_date}", headers=self.headers)
        return response.json()

    def get_current_price(self, symbol):
        # Implement current price retrieval
        response = requests.get(f"https://api.tradier.com/v1/markets/quotes?symbols={symbol}", headers=self.headers)
        return response.json().get('last')
