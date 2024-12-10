import requests
import time
from brokers.base_broker import BaseBroker
from utils.logger import logger  # Import the logger
from utils.utils import extract_underlying_symbol
import aiohttp


class TradierBroker(BaseBroker):
    def __init__(self, api_key, secret_key, engine, **kwargs):
        super().__init__(api_key, secret_key, 'Tradier', engine=engine, **kwargs)
        self.base_url = 'https://api.tradier.com/v1'
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        self.order_timeout = kwargs.get('order_timeout', 5)
        self.auto_cancel_orders = kwargs.get('auto_cancel_orders', False)
        logger.info('Initialized TradierBroker',
                    extra={'base_url': self.base_url})
        self._get_account_info()

    def connect(self):
        logger.info('Connecting to Tradier API')
        # Placeholder for actual connection logic
        pass

    def _get_account_info(self):
        logger.debug('Retrieving account information')
        try:
            response = requests.get(
                "https://api.tradier.com/v1/user/profile", headers=self.headers)
            response.raise_for_status()
            account_info = response.json()
            account_id = account_info['profile']['account']['account_number']
            self.account_id = account_id
            logger.info('Account info retrieved', extra={
                        'account_id': self.account_id})

            url = f'{self.base_url}/accounts/{self.account_id}/balances'
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            account_info = response.json().get('balances')

            if not account_info:
                logger.error("Invalid account info response")

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
                account_value = account_info['total_equity']
            cash = account_info['total_cash']

            logger.debug('Account balances retrieved', extra={
                        'account_type': self.account_type, 'buying_power': buying_power, 'value': account_value})
            return {
                'account_number': account_info['account_number'],
                'account_type': self.account_type,
                'buying_power': buying_power,
                'cash': cash,
                'value': account_value
            }
        except requests.RequestException as e:
            logger.error('Failed to retrieve account information',
                         extra={'error': str(e)})

    def get_positions(self):
        logger.info('Retrieving positions')
        url = f"{self.base_url}/accounts/{self.account_id}/positions"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            positions_data = response.json()['positions']
            if positions_data == 'null':
                return {}
            else:
                positions_data = positions_data.get('position', None)
            if not positions_data:
                return {}

            if type(positions_data) != list:
                positions_data = [positions_data]
            positions = {p['symbol']: p for p in positions_data}
            logger.info('Positions retrieved', extra={'positions': positions})
            return positions
        except requests.RequestException as e:
            logger.error('Failed to retrieve positions',
                         extra={'error': str(e)})

    async def _is_order_filled(self, order_id):
        logger.info('Checking if order is filled', extra={'order_id': order_id})
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(
                    f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}"
                ) as response:
                    if response.status != 200:
                        logger.error(
                            'Failed to retrieve order status',
                            extra={'error': f"HTTP status code {response.status}"}
                        )
                        return False
                    data = await response.json()
                    order_status = data['order']['status']
                    logger.info(
                        'Order status retrieved',
                        extra={'order_status': order_status}
                    )
                    return order_status == 'filled'
        except aiohttp.ClientError as e:
            logger.error(
                'Failed to retrieve order status',
                extra={'error': str(e)}
            )
            return False

    def _place_order(self, symbol, quantity, side, price=None, order_type='limit'):
        logger.info('Placing order', extra={
                    'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price})
        try:
            if price is None:
                quote_url = f"https://api.tradier.com/v1/markets/quotes?symbols={symbol}"
                quote_response = requests.get(quote_url, headers=self.headers)
                quote_response.raise_for_status()
                quote = quote_response.json()['quotes']['quote']
                bid = quote['bid']
                ask = quote['ask']
                price = round((bid + ask) / 2, 2)

            if order_type == 'limit':
                order_data = {
                    "class": "equity",
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "type": "limit",
                    "duration": "day",
                    "price": price
                }
            elif order_type == 'market':
                order_data = {
                    "class": "equity",
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "type": "market",
                    "duration": "day"
                }
            else:
                logger.error('Invalid order type', extra={
                             'order_type': order_type, 'symbol': symbol})
                return

            # TODO: fix/remove
            response = requests.post(
                f"{self.base_url}/accounts/{self.account_id}/orders", data=order_data, headers=self.headers)
            if response.status_code != 200:
                # Assume the order worked anyway because
                # the response is not always correct (Tradier confusing)
                logger.error('Failed to place order', extra={
                             'response': response.text})
            # TODO: refactor/remove
            try:
                order_json = response.json()
            except Exception as e:
                # Again, Tradier is weird...
                logger.error('Failed to parse order response',
                             extra={'error': str(e)})
                order_json = {}

            order_id = order_json.get('order', {}).get('id', None)
            logger.info('Order placed', extra={'order_id': order_id})

            if self.auto_cancel_orders and order_id is not None:
                time.sleep(self.order_timeout)
                order_status_url = f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}"
                status_response = requests.get(
                    order_status_url, headers=self.headers)
                order_status = status_response.json()['order']['status']

                if order_status != 'filled':
                    try:
                        cancel_url = f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}/cancel"
                        cancel_response = requests.put(
                            cancel_url, headers=self.headers)
                        cancel_response.raise_for_status()
                        logger.info('Order cancelled', extra={
                                    'order_id': order_id})
                    except requests.RequestException as e:
                        logger.error('Failed to cancel order',
                                     extra={'order_id': order_id})

            data = order_json or {}
            if data.get('filled_price') is None:
                data['filled_price'] = price
            data['order_id'] = order_id
            logger.info('Order execution complete', extra={'order_data': data})
            return data
        except Exception as e:
            logger.error('Failed to place order', extra={'error': str(e)})
            return {}

    def _place_future_option_order(self, symbol, quantity, side, price=None):
        logger.error('Future options not supported by Tradier',
                     extra={'symbol': symbol})
        raise NotImplementedError

    def _place_option_order(self, symbol, quantity, side, price=None):
        ticker = extract_underlying_symbol(symbol)
        logger.info('Placing option order', extra={
                    'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price})
        # Sane conversions
        if side == 'buy':
            side = 'buy_to_open'
        elif side == 'sell':
            side = 'sell_to_close'
        try:
            if price is None:
                quote_url = f"https://api.tradier.com/v1/markets/quotes?symbols={symbol}"
                quote_response = requests.get(quote_url, headers=self.headers)
                quote_response.raise_for_status()
                quote = quote_response.json()['quotes']['quote']
                bid = quote['bid']
                ask = quote['ask']
                price = round((bid + ask) / 2, 2)

            order_data = {
                "class": "option",
                "symbol": ticker,
                "option_symbol": symbol,
                "quantity": quantity,
                "side": side,
                "type": "limit",
                "duration": "day",
                "price": price
            }

            response = requests.post(
                f"{self.base_url}/accounts/{self.account_id}/orders", data=order_data, headers=self.headers)
            if response.status_code != 200:
                # Assume the order worked anyway because
                # the response is not always correct (Tradier confusing)
                logger.error('Failed to place order', extra={
                             'response': response.text})

            # TODO: refactor/remove
            try:
                order_json = response.json()
            except Exception as e:
                # Again, Tradier is weird...
                logger.error('Failed to parse order response',
                             extra={'error': str(e)})
                order_json = {}

            order_id = order_json.get('order', {}).get('id', None)
            logger.info('Order placed', extra={'order_id': order_id})

            if self.auto_cancel_orders:
                time.sleep(self.order_timeout)
                order_status_url = f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}"
                status_response = requests.get(
                    order_status_url, headers=self.headers)
                status_response.raise_for_status()
                order_status = status_response.json()['order']['status']

                if order_status != 'filled':
                    try:
                        cancel_url = f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}/cancel"
                        cancel_response = requests.put(
                            cancel_url, headers=self.headers)
                        cancel_response.raise_for_status()
                        logger.info('Order cancelled', extra={
                                    'order_id': order_id})
                        return None
                    except requests.RequestException as e:
                        logger.error('Failed to cancel order',
                                     extra={'order_id': order_id})

            data = order_json or {}
            if data.get('filled_price') is None:
                data['filled_price'] = price
            logger.info('Order execution complete', extra={'order_data': data})
            return data
        except Exception as e:
            logger.error('Failed to place order', extra={'error': str(e)})
            return {}

    def _get_order_status(self, order_id):
        logger.info('Retrieving order status', extra={'order_id': order_id})
        try:
            response = requests.get(
                f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}", headers=self.headers)
            response.raise_for_status()
            order_status = response.json()
            logger.info('Order status retrieved', extra={
                        'order_status': order_status})
            return order_status
        except requests.RequestException as e:
            logger.error('Failed to retrieve order status',
                         extra={'error': str(e)})

    def _cancel_order(self, order_id):
        logger.info('Cancelling order', extra={'order_id': order_id})
        try:
            response = requests.delete(
                f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}", headers=self.headers)
            response.raise_for_status()
            cancellation_response = response.json()
            logger.info('Order cancelled successfully', extra={
                        'cancellation_response': cancellation_response})
            return cancellation_response
        except requests.RequestException as e:
            logger.error('Failed to cancel order', extra={'error': str(e)})

    def _get_options_chain(self, symbol, expiration_date):
        logger.info('Retrieving options chain', extra={
                    'symbol': symbol, 'expiration_date': expiration_date})
        try:
            response = requests.get(
                f"{self.base_url}/markets/options/chains?symbol={symbol}&expiration={expiration_date}", headers=self.headers)
            response.raise_for_status()
            options_chain = response.json()
            logger.info('Options chain retrieved', extra={
                        'options_chain': options_chain})
            return options_chain
        except requests.RequestException as e:
            logger.error('Failed to retrieve options chain',
                         extra={'error': str(e)})

    async def get_mid_price(self, symbol):
        logger.info('Retrieving mid price', extra={'symbol': symbol})
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/markets/quotes?symbols={symbol}", headers=self.headers) as response:
                    response.raise_for_status()
                    data = await response.json()
                    bid = data.get('quotes', {}).get('quote', {}).get('bid')
                    ask = data.get('quotes', {}).get('quote', {}).get('ask')
                    mid_price = round((bid + ask) / 2, 2)
                    logger.info('Mid price retrieved', extra={'symbol': symbol, 'mid_price': mid_price})
                    return mid_price
        except aiohttp.ClientError as e:
            logger.error('Failed to retrieve mid price', extra={'error': str(e)})

    async def get_current_price(self, symbol):
        logger.info('Retrieving current price', extra={'symbol': symbol})
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/markets/quotes?symbols={symbol}", headers=self.headers) as response:
                    response.raise_for_status()
                    data = await response.json()
                    last_price = data.get('quotes', {}).get('quote', {}).get('last')
                    logger.info('Current price retrieved', extra={'symbol': symbol, 'last_price': last_price})
                    return last_price
        except aiohttp.ClientError as e:
            logger.error('Failed to retrieve current price', extra={'error': str(e)})


    def get_bid_ask(self, symbol):
        logger.info('Retrieving bid/ask', extra={'symbol': symbol})
        try:
            response = requests.get(
                f"{self.base_url}/markets/quotes?symbols={symbol}", headers=self.headers)
            response.raise_for_status()
            quote = response.json().get('quotes').get('quote')
            bid = quote.get('bid')
            ask = quote.get('ask')
            logger.info('Bid/ask retrieved',
                        extra={'symbol': symbol, 'bid': bid, 'ask': ask})
            return {'bid': bid, 'ask': ask}
        except requests.RequestException as e:
            logger.error('Failed to retrieve bid/ask', extra={'error': str(e)})

    def get_cost_basis(self, symbol):
        logger.info(f'Retrieving cost basis for symbol {symbol} from Tradier')
        try:
            positions = self.get_positions()
            if not positions:
                logger.error(f"No positions found for symbol {symbol}")
                return None
            position = positions.get(symbol)
            if not position:
                logger.error(f"No position found for symbol {symbol}")
                return None
            cost_basis = position.get('cost_basis')
            logger.info(f"Cost basis for {symbol} is {cost_basis}")
            return cost_basis
        except requests.RequestException as e:
            logger.error(
                f"Failed to retrieve cost basis for {symbol}: {str(e)}")
            return None
