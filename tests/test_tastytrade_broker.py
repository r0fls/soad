import requests
import time
import json
import re
from decimal import Decimal
from brokers.base_broker import BaseBroker
from utils.logger import logger
from utils.utils import extract_underlying_symbol, is_ticker, is_option, is_futures_symbol
from tastytrade import session, DXLinkStreamer, Account
from tastytrade.instruments import Equity, NestedOptionChain, Option, Future, FutureOption
from tastytrade.dxfeed import EventType
from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType, PriceEffect, OrderStatus

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
        self.session = None
        self.connect()
        self._get_account_info()

    @staticmethod
    def format_option_symbol(option_symbol):
        match = re.match(r'^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$', option_symbol)
        if not match:
            raise ValueError("Invalid option symbol format")
        underlying = match.group(1)
        rest_of_symbol = ''.join(match.groups()[1:])
        formatted_symbol = f"{underlying:<6}{rest_of_symbol}"
        return formatted_symbol

    async def get_option_chain(self, underlying_symbol):
        try:
            option_chain = await NestedOptionChain.get(self.session, underlying_symbol)
            return option_chain
        except Exception as e:
            logger.error(f"Error fetching option chain for {underlying_symbol}: {e}")
            return None

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
        self.session = session(self.username, self.password)
        logger.info('Connected to Tastytrade API')

    def _get_account_info(self, retry=True):
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
            cash = account_data.get('cash-balance')

            logger.info('Account balances retrieved', extra={'buying_power': buying_power, 'value': account_value})
            return {
                'account_number': self.account_id,
                'buying_power': float(buying_power),
                'cash': float(cash),
                'value': float(account_value)
            }
        except requests.RequestException as e:
            logger.error('Failed to retrieve account information', extra={'error': str(e)})
            if retry:
                self.connect()
                return self._get_account_info(retry=False)

    async def _place_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        try:
            last_price = await self.get_current_price(symbol)
            if price is None:
                price = round(last_price, 2)
            quantity = Decimal(quantity)
            price = Decimal(price)

            if order_type.lower() == 'buy':
                action = OrderAction.BUY_TO_OPEN
                price_effect = PriceEffect.DEBIT
            elif order_type.lower() == 'sell':
                action = OrderAction.SELL_TO_CLOSE
                price_effect = PriceEffect.CREDIT
            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            account = Account.get_account(self.session, self.account_id)
            symbol = Equity.get_equity(self.session, symbol)
            leg = symbol.build_leg(quantity, action)

            order = NewOrder(
                time_in_force=OrderTimeInForce.DAY,
                order_type=OrderType.LIMIT,
                legs=[leg],
                price=price,
                price_effect=price_effect
            )

            response = account.place_order(self.session, order, dry_run=False)

            if getattr(response, 'errors', None):
                logger.error('Order placement failed with no order ID', extra={'response': str(response)})
                return {'filled_price': None}
            else:
                if self.is_order_filled(response):
                    logger.info('Order filled', extra={'response': str(response)})
                else:
                    logger.info('Order likely still open', extra={'order_data': response})
                return {'filled_price': price, 'order_id': getattr(response, 'id', 0)}

        except Exception as e:
            logger.error('Failed to place order', extra={'error': str(e)})
            return {'filled_price': None}

    async def get_current_price(self, symbol):
        async with DXLinkStreamer(self.session) as streamer:
            try:
                subs_list = [symbol]
                await streamer.subscribe(EventType.QUOTE, subs_list)
                quote = await streamer.get_event(EventType.QUOTE)
                return round(float((quote.bidPrice + quote.askPrice) / 2), 2)
            finally:
                await streamer.close()

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
