import requests
import time
import json
import re
from decimal import Decimal
from brokers.base_broker import BaseBroker
from utils.logger import logger
from utils.utils import extract_underlying_symbol, is_ticker, is_option, is_futures_symbol
from tastytrade import Session, DXLinkStreamer, Account
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
        logger.info('Initialized TastytradeBroker',
                    extra={'base_url': self.base_url})
        self.session = None
        self.connect()
        self._get_account_info()

    @staticmethod
    def format_option_symbol(option_symbol):
        match = re.match(
            r'^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$', option_symbol)
        if not match:
            raise ValueError("Invalid option symbol format")

        underlying = match.group(1)
        rest_of_symbol = ''.join(match.groups()[1:])
        formatted_symbol = f"{underlying:<6}{rest_of_symbol}"
        return formatted_symbol

    async def get_option_chain(self, underlying_symbol):
        """
        Fetch the option chain for a given underlying symbol.

        Args:
            session: Tastytrade API session.
            underlying_symbol: The underlying symbol for which to fetch the option chain.

        Returns:
            An OptionChain object containing the option chain data.
        """
        try:
            option_chain = await NestedOptionChain.get(self.session, underlying_symbol)
            return option_chain
        except Exception as e:
            logger.error(
                f"Error fetching option chain for {underlying_symbol}: {e}")
            return None

    def connect(self):
        logger.info('Connecting to Tastytrade API')
        auth_data = {
            "login": self.username,
            "password": self.password,
            "remember-me": True
        }
        response = requests.post(
            f"{self.base_url}/sessions", json=auth_data, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        auth_response = response.json().get('data')
        self.auth = auth_response['session-token']
        self.headers["Authorization"] = self.auth
        # Refresh the session
        self.session = Session(self.username, self.password)
        logger.info('Connected to Tastytrade API')

    def _get_account_info(self, retry=True):
        logger.debug('Retrieving account information')
        try:
            response = requests.get(
                f"{self.base_url}/customers/me/accounts", headers=self.headers)
            response.raise_for_status()
            account_info = response.json()
            account_id = account_info['data']['items'][0]['account']['account-number']
            self.account_id = account_id
            logger.info('Account info retrieved', extra={
                        'account_id': self.account_id})

            response = requests.get(
                f"{self.base_url}/accounts/{self.account_id}/balances", headers=self.headers)
            response.raise_for_status()
            account_data = response.json().get('data')

            if not account_data:
                logger.error("Invalid account info response")

            buying_power = account_data['equity-buying-power']
            account_value = account_data['net-liquidating-value']
            account_type = None

            # TODO: is this redundant? Can we collapse/remove the above API calls?
            cash = account_data.get('cash-balance')

            logger.debug('Account balances retrieved', extra={
                        'account_type': account_type, 'buying_power': buying_power, 'value': account_value})
            return {
                'account_number': self.account_id,
                'account_type': account_type,
                'buying_power': float(buying_power),
                'cash': float(cash),
                'value': float(account_value)
            }
        except requests.RequestException as e:
            logger.error('Failed to retrieve account information',
                         extra={'error': str(e)})
            if retry:
                logger.info('Trying to authenticate again')
                self.connect()
                return self._get_account_info(retry=False)

    def get_positions(self, retry=True):
        logger.info('Retrieving positions')
        url = f"{self.base_url}/accounts/{self.account_id}/positions"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            positions_data = response.json()['data']['items']
            positions = {self.process_symbol(
                p['symbol']): p for p in positions_data}
            logger.info('Positions retrieved', extra={'positions': positions})
            return positions
        except requests.RequestException as e:
            logger.error('Failed to retrieve positions',
                         extra={'error': str(e)})
            if retry:
                logger.info('Trying to authenticate again')
                self.connect()
                return self.get_positions(retry=False)

    @staticmethod
    def process_symbol(symbol):
        # NOTE: Tastytrade API returns options positions with spaces in the symbol.
        # Standardize them here. However this is not worth doing for futures options,
        # since they're the only current broker that supports them.
        if is_futures_symbol(symbol):
            return symbol
        else:
            return symbol.replace(' ', '')  # Remove spaces from the symbol

    @staticmethod
    def check_is_order_filled_from_response(order_response):
        if order_response.order.status == OrderStatus.FILLED:
            return True

        for leg in order_response.order.legs:
            if leg.remaining_quantity > 0:
                return False
            if not leg.fills:
                return False

        return True

    async def _place_future_option_order(self, symbol, quantity, side, price=None, order_type='limit'):
        ticker = extract_underlying_symbol(symbol)
        logger.info('Placing future option order', extra={
                    'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
        option = FutureOption.get_future_option(self.session, symbol)
        if price is None:
            price = await self.get_current_price(symbol)
            price = round(price * 4) / 4
            logger.info(
                'Price not provided, using mid from current bid/ask', extra={'price': price})
        if side == 'buy':
            action = OrderAction.BUY_TO_OPEN
            effect = PriceEffect.DEBIT
        elif side == 'sell':
            action = OrderAction.SELL_TO_CLOSE
            effect = PriceEffect.CREDIT
        account = Account.get_account(self.session, self.account_id)
        leg = option.build_leg(quantity, action)
        if order_type == 'limit':
            order = NewOrder(
                time_in_force=OrderTimeInForce.DAY,
                order_type=OrderType.LIMIT,
                legs=[leg],
                price=Decimal(price),
                price_effect=effect
            )
        elif order_type == 'market':
            order = NewOrder(
                time_in_force=OrderTimeInForce.DAY,
                order_type=OrderType.MARKET,
                legs=[leg],
                price=Decimal(price),
                price_effect=effect
            )
        else:
            logger.error(f"Unsupported order type: {order_type}", extra={
                         'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
            return {'filled_price': None}

        response = account.place_order(self.session, order, dry_run=False)
        return response

    async def _place_option_order(self, symbol, quantity, side, price=None, order_type='limit'):
        ticker = extract_underlying_symbol(symbol)
        logger.info('Placing option order', extra={
                    'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
        if ' ' not in symbol:
            symbol = self.format_option_symbol(symbol)
        if price is None:
            price = await self.get_current_price(symbol)
        if side == 'buy':
            action = OrderAction.BUY_TO_OPEN
            effect = PriceEffect.DEBIT
        elif side == 'sell':
            action = OrderAction.SELL_TO_CLOSE
            effect = PriceEffect.CREDIT
        account = Account.get_account(self.session, self.account_id)
        option = Option.get_option(self.session, symbol)
        leg = option.build_leg(quantity, action)
        if order_type == 'limit':
            order = NewOrder(
                time_in_force=OrderTimeInForce.DAY,
                order_type=OrderType.LIMIT,
                legs=[leg],
                price=Decimal(price),
                price_effect=effect
            )
        elif order_type == 'market':
            order = NewOrder(
                time_in_force=OrderTimeInForce.DAY,
                order_type=OrderType.MARKET,
                legs=[leg],
                price_effect=effect
            )
        else:
            logger.error(f"Unsupported order type: {order_type}", extra={
                         'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
            return {'filled_price': None}

        response = account.place_order(self.session, order, dry_run=False)
        # TODO: refactor as part of introducing generic order method
        if hasattr(response, 'order'):
            return response.order
        return response

    async def _place_order(self, symbol, quantity, side, price=None, order_type='limit'):
        logger.info('Placing order', extra={
                    'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
        try:
            if price is None or order_type != 'market':
                last_price = await self.get_current_price(symbol)
                price = round(last_price, 2)

            # Convert to Decimal
            quantity = Decimal(quantity)
            price = Decimal(price)

            # Map side to OrderAction
            # TODO: fix order action for short sales,
            # though it seems to be working anyway
            if side.lower() == 'buy':
                action = OrderAction.BUY_TO_OPEN
                price_effect = PriceEffect.DEBIT
            # TODO: this maps tradier side to tastytrade side
            # abstract/move this logic to a separate locationt
            elif side.lower() == 'buy_to_cover':
                action = OrderAction.BUY_TO_CLOSE
                price_effect = PriceEffect.DEBIT
            elif side.lower() == 'sell':
                action = OrderAction.SELL_TO_CLOSE
                price_effect = PriceEffect.CREDIT
            # TODO: this maps tradier side to tastytrade side
            # abstract/move this logic to a separate location
            elif side.lower() == 'sell_short':
                action = OrderAction.SELL_TO_OPEN
                price_effect = PriceEffect.CREDIT
            else:
                raise ValueError(f"Unsupported order type: {side}")

            account = Account.get_account(self.session, self.account_id)
            symbol = Equity.get_equity(self.session, symbol)
            leg = symbol.build_leg(quantity, action)

            if order_type == 'limit':
                order = NewOrder(
                    time_in_force=OrderTimeInForce.DAY,
                    order_type=OrderType.LIMIT,
                    legs=[leg],
                    price=price,
                    price_effect=price_effect
                )
            elif order_type == 'market':
                order = NewOrder(
                    time_in_force=OrderTimeInForce.DAY,
                    order_type=OrderType.MARKET,
                    legs=[leg],
                    price_effect=price_effect
                )
            else:
                logger.error(f"Unsupported order type: {order_type}", extra={
                             'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
                return {'filled_price': None}

            response = account.place_order(self.session, order, dry_run=False)

            if getattr(response, 'errors', None):
                logger.error('Order placement failed with no order ID', extra={'response': str(
                    response), 'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
                return {'filled_price': None}
            else:
                if self.check_is_order_filled_from_response(response):
                    logger.info('Order filled', extra={'response': str(
                        response), 'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
                else:
                    logger.info('Order likely still open', extra={
                                'order_data': response, 'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
                if hasattr(response, 'order'):
                    return {'filled_price': price, 'order_id': response.order.id}
                else:
                    logger.error('Order placement failed', extra={'response': str(
                        response), 'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
                    return response

        except Exception as e:
            logger.error('Failed to place order', extra={'error': str(e)})
            return {'filled_price': None}

    def _is_order_filled(self, order_id):
        status = self._get_order_status(order_id)
        if status is None:
            return False
        all_legs_filled = all(
                [leg.get('remaining-quantity') == 0 for leg in status.get('data').get('legs')]
            )
        return all_legs_filled

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
            # Raise so that the caller knows to perform a credential refresh
            raise

    def _cancel_order(self, order_id):
        logger.info('Cancelling order', extra={'order_id': order_id})
        try:
            account = Account.get_account(self.session, self.account_id)
            account.delete_order(self.session, order_id)
            logger.info('Order cancelled successfully')
        except requests.RequestException as e:
            logger.error('Failed to cancel order', extra={'error': str(e)})

    def _get_options_chain(self, symbol, expiration_date):
        logger.info('Retrieving options chain', extra={
                    'symbol': symbol, 'expiration_date': expiration_date})
        try:
            response = requests.get(f"{self.base_url}/markets/options/chains", params={
                                    "symbol": symbol, "expiration": expiration_date}, headers=self.headers)
            response.raise_for_status()
            options_chain = response.json()
            logger.info('Options chain retrieved', extra={
                        'options_chain': options_chain})
            return options_chain
        except requests.RequestException as e:
            logger.error('Failed to retrieve options chain',
                         extra={'error': str(e)})

    async def get_current_price(self, symbol):
        # TODO: get last instead of mid
        return self.get_mid_price(symbol)

    async def get_mid_price(self, symbol):
        if ':' in symbol:
            # Looks like this is already a streamer symbol
            pass
        elif is_futures_symbol(symbol):
            logger.info('Getting current price for futures symbol',
                        extra={'symbol': symbol})
            option = FutureOption.get_future_option(self.session, symbol)
            symbol = option.streamer_symbol
        elif is_option(symbol):
            # Convert to streamer symbol
            if ' ' not in symbol:
                symbol = self.format_option_symbol(symbol)
            if '.' not in symbol:
                symbol = Option.occ_to_streamer_symbol(symbol)
        async with DXLinkStreamer(self.session) as streamer:
            try:
                subs_list = [symbol]
                await streamer.subscribe(EventType.QUOTE, subs_list)
                quote = await streamer.get_event(EventType.QUOTE)
                return round(float((quote.bidPrice + quote.askPrice) / 2), 2)
            finally:
                await streamer.close()

    async def get_bid_ask(self, symbol):
        if ':' in symbol:
            # Looks like this is already a streamer symbol
            pass
        elif is_futures_symbol(symbol):
            logger.info('Getting current price for futures symbol',
                        extra={'symbol': symbol})
            option = FutureOption.get_future_option(self.session, symbol)
            symbol = option.streamer_symbol
        elif is_option(symbol):
            # Convert to streamer symbol
            if ' ' not in symbol:
                symbol = self.format_option_symbol(symbol)
            if '.' not in symbol:
                symbol = Option.occ_to_streamer_symbol(symbol)
        async with DXLinkStreamer(self.session) as streamer:
            try:
                subs_list = [symbol]
                await streamer.subscribe(EventType.QUOTE, subs_list)
                quote = await streamer.get_event(EventType.QUOTE)
                return {"bid": quote.bidPrice, "ask": quote.askPrice}
            finally:
                await streamer.close()

    def get_cost_basis(self, symbol):
        logger.info(
            f'Retrieving cost basis for symbol {symbol} from Tastytrade')
        try:
            url = f"{self.base_url}/accounts/{self.account_id}/positions"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            positions_data = response.json()['data']['items']

            for position in positions_data:
                if position['symbol'] == symbol:
                    open_price = position.get('average-open-price')
                    quantity = position.get('quantity')
                    if open_price and quantity:
                        cost_basis = open_price * quantity
                        logger.info(f"Cost basis for {symbol}: {cost_basis}")
                        return cost_basis
                    else:
                        logger.warning(f"Cost basis not found for {symbol}")
                        return None
            logger.warning(f"No position found for {symbol}")
            return None
        except requests.RequestException as e:
            logger.error(
                f"Failed to retrieve cost basis for {symbol}: {str(e)}")
            return None
