import requests
import time
from brokers.base_broker import BaseBroker

class TradierBroker(BaseBroker):
    def __init__(self, api_key, secret_key, engine, **kwargs):
        super().__init__(api_key, secret_key, 'Tradier', engine, **kwargs)
        self.base_url = 'https://api.tradier.com/v1'
        self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
        }
        self.order_timeout = 1
        self.auto_cancel_orders = True

    # TODO: remove
    def connect(self):
        pass

    def _get_account_info(self):
        # Implement account information retrieval
        response = requests.get("https://api.tradier.com/v1/user/profile", headers=self.headers)
        if response.status_code == 401:
            raise ValueError("It seems we are having trouble authenticating to Tradier")
        account_info = response.json()
        account_id = account_info['profile']['account']['account_number']
        self.account_id = account_id

        # Get the balance info for the account
        url = f'{self.base_url}/accounts/{self.account_id}/balances'
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Failed to get account info: {response.text}")

        account_info = response.json().get('balances')
        if not account_info:
            raise Exception("Invalid account info response")

        if account_info.get('cash'):
            self.account_type = 'cash'
            buying_power = account_info['cash']['cash_available']
            account_value = account_info['total_equity']
        if account_info.get('margin'):
            self.account_type = 'margin'
            buying_power = account_info['margin']['stock_buying_power']
            account_value = account_info['total_equity']
        if account_info.get('pdt'):
            self.account_type = 'pdt'
            buying_power = account_info['pdt']['stock_buying_power']

        return {
            'account_number': account_info['account_number'],
            'account_type': self.account_type,
            'buying_power': buying_power,
            'value': account_value
        }

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
        # Retrieve the current quote to get the bid/ask prices
        quote_url = f"https://api.tradier.com/v1/markets/quotes?symbols={symbol}"
        quote_response = requests.get(quote_url, headers=self.headers)
        if quote_response.status_code != 200:
            raise Exception(f"Failed to get quote: {quote_response.text}")

        quote = quote_response.json()['quotes']['quote']
        bid = quote['bid']
        ask = quote['ask']

        # Use the median of the bid/ask spread as the limit price if none is provided
        if price is None:
            price = round((bid + ask) / 2, 2)

        # Prepare order data
        order_data = {
            "class": "equity",
            "symbol": symbol,
            "quantity": quantity,
            "side": order_type,  # 'buy' or 'sell'
            "type": "limit",  # Using limit order type
            "duration": "day",  # Immediate or Cancel
            "price": price
        }

        # Make the API call to place the order
        response = requests.post(f"https://api.tradier.com/v1/accounts/{self.account_id}/orders", data=order_data, headers=self.headers)

        # Check for success or raise an exception
        if response.status_code > 400:
            print(f"Failed to place order: {response.text}")
            return {}

        order_id = response.json()['order']['id']
        if self.auto_cancel_orders:
            # Wait for a short period to check if the order gets filled
            time.sleep(self.order_timeout)

            # Check the order status
            order_status_url = f"https://api.tradier.com/v1/accounts/{self.account_id}/orders/{order_id}"
            status_response = requests.get(order_status_url, headers=self.headers)
            if status_response.status_code != 200:
                raise Exception(f"Failed to get order status: {status_response.text}")

            order_status = status_response.json()['order']['status']

            # Cancel the order if it's not filled
            if order_status != 'filled':
                cancel_url = f"https://api.tradier.com/v1/accounts/{self.account_id}/orders/{order_id}/cancel"
                cancel_response = requests.put(cancel_url, headers=self.headers)
                if cancel_response.status_code != 200:
                    raise Exception(f"Failed to cancel order: {cancel_response.text}")

        # Return the response in JSON format
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
        last_price = response.json().get('quotes').get('quote').get('last')
        return last_price
