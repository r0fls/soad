import time
from brokers.base_broker import BaseBroker
from webull import webull
from utils.logger import logger  # Import the logger

class WebullBroker(BaseBroker):
    def __init__(self, api_key, secret_key, engine, **kwargs):
        super().__init__(api_key, secret_key, 'Webull', engine=engine, **kwargs)
        self.wb = webull()
        self.order_timeout = 1
        self.auto_cancel_orders = True
        self.account_id = None
        logger.info('Initialized WebullBroker')

    def connect(self, username, password):
        logger.info('Connecting to Webull API')
        try:
            self.wb.login(username, password)
            logger.info('Successfully connected to Webull API')
        except Exception as e:
            logger.error('Failed to connect to Webull API', extra={'error': str(e)})

    def _get_account_info(self):
        logger.info('Retrieving account information')
        try:
            account_info = self.wb.get_account()
            self.account_id = account_info['secAccountId']

            balances = self.wb.get_account()
            account_type = balances.get('accountType')
            buying_power = balances.get('buyingPower')
            account_value = balances.get('totalAccountValue')
            cash = balances.get('cashBalance')

            logger.info('Account balances retrieved', extra={'account_type': account_type, 'buying_power': buying_power, 'value': account_value})
            return {
                'account_number': self.account_id,
                'account_type': account_type,
                'buying_power': buying_power,
                'cash': cash,
                'value': account_value
            }
        except Exception as e:
            logger.error('Failed to retrieve account information', extra={'error': str(e)})

    def get_positions(self):
        logger.info('Retrieving positions')
        try:
            positions_data = self.wb.get_positions()
            positions = {p['ticker']['symbol']: p for p in positions_data}
            logger.info('Positions retrieved', extra={'positions': positions})
            return positions
        except Exception as e:
            logger.error('Failed to retrieve positions', extra={'error': str(e)})

    def _place_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        try:
            if price is None:
                quote = self.wb.get_quote(symbol)
                bid = quote['bidPrice']
                ask = quote['askPrice']
                price = round((bid + ask) / 2, 2)

            order_id = self.wb.place_order(stock=symbol, action=order_type.upper(), orderType='LMT', enforce='DAY', qty=quantity, price=price)
            logger.info('Order placed', extra={'order_id': order_id})

            if self.auto_cancel_orders:
                time.sleep(self.order_timeout)
                order_status = self.wb.get_order_status(order_id)
                if order_status != 'Filled':
                    try:
                        self.wb.cancel_order(order_id)
                        logger.info('Order cancelled', extra={'order_id': order_id})
                    except Exception as e:
                        logger.error('Failed to cancel order', extra={'order_id': order_id})

            return {'order_id': order_id, 'filledPrice': price}
        except Exception as e:
            logger.error('Failed to place order', extra={'error': str(e)})

    def _place_option_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing option order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        try:
            if price is None:
                quote = self.wb.get_options_quote(symbol)
                bid = quote['bidPrice']
                ask = quote['askPrice']
                price = round((bid + ask) / 2, 2)

            order_id = self.wb.place_option_order(stock=symbol, action=order_type.upper(), orderType='LMT', enforce='DAY', qty=quantity, price=price)
            logger.info('Order placed', extra={'order_id': order_id})

            if self.auto_cancel_orders:
                time.sleep(self.order_timeout)
                order_status = self.wb.get_order_status(order_id)
                if order_status != 'Filled':
                    try:
                        self.wb.cancel_order(order_id)
                        logger.info('Order cancelled', extra={'order_id': order_id})
                    except Exception as e:
                        logger.error('Failed to cancel order', extra={'order_id': order_id})

            return {'order_id': order_id, 'filledPrice': price}
        except Exception as e:
            logger.error('Failed to place option order', extra={'error': str(e)})

    def _get_order_status(self, order_id):
        logger.info('Retrieving order status', extra={'order_id': order_id})
        try:
            order_status = self.wb.get_order_status(order_id)
            logger.info('Order status retrieved', extra={'order_status': order_status})
            return order_status
        except Exception as e:
            logger.error('Failed to retrieve order status', extra={'error': str(e)})

    def _cancel_order(self, order_id):
        logger.info('Cancelling order', extra={'order_id': order_id})
        try:
            cancellation_response = self.wb.cancel_order(order_id)
            logger.info('Order cancelled successfully', extra={'cancellation_response': cancellation_response})
            return cancellation_response
        except Exception as e:
            logger.error('Failed to cancel order', extra={'error': str(e)})

    def _get_options_chain(self, symbol, expiration_date):
        logger.info('Retrieving options chain', extra={'symbol': symbol, 'expiration_date': expiration_date})
        try:
            options_chain = self.wb.get_options(symbol, expiration=expiration_date)
            logger.info('Options chain retrieved', extra={'options_chain': options_chain})
            return options_chain
        except Exception as e:
            logger.error('Failed to retrieve options chain', extra={'error': str(e)})

    def get_current_price(self, symbol):
        logger.info('Retrieving current price', extra={'symbol': symbol})
        try:
            quote = self.wb.get_quote(symbol)
            last_price = quote.get('lastPrice')
            logger.info('Current price retrieved', extra={'symbol': symbol, 'last_price': last_price})
            return last_price
        except Exception as e:
            logger.error('Failed to retrieve current price', extra={'error': str(e)})

