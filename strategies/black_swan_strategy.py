import random
from datetime import timedelta, datetime
from database.models import Balance, Trade
from utils.utils import is_market_open
from utils.logger import logger
from strategies.base_strategy import BaseStrategy
import asyncio
import yfinance as yf
import pandas as pd

class BlackSwanStrategy(BaseStrategy):
    def __init__(self, broker, strategy_name, rebalance_interval_minutes, starting_capital, symbol="SPY", otm_percentage=0.05, expiry_days=30, bet_percentage=0.1, holding_period_days=7, spike_percentage=500):
        self.rebalance_interval_minutes = rebalance_interval_minutes
        self.rebalance_interval = timedelta(minutes=rebalance_interval_minutes)
        self.symbol = symbol
        self.otm_percentage = otm_percentage
        self.expiry_days = expiry_days
        self.bet_percentage = bet_percentage
        self.holding_period_days = holding_period_days
        self.spike_percentage = spike_percentage
        super().__init__(broker, strategy_name, starting_capital)
        logger.info(
            f"Initialized {self.strategy_name} strategy with starting capital {self.starting_capital}")

    async def initialize(self):
        pass

    async def rebalance(self):
        logger.debug("Starting rebalance process")

        with self.broker.Session() as session:
            balance = session.query(Balance).filter_by(
                strategy=self.strategy_name,
                broker=self.broker.broker_name,
                type='cash'
            ).order_by(Balance.timestamp.desc()).first()
            if balance is None:
                logger.error(
                    f"Strategy balance not initialized for {self.strategy_name} strategy on {self.broker.broker_name}.")
                raise ValueError(
                    f"Strategy balance not initialized for {self.strategy_name} strategy on {self.broker.broker_name}.")
            total_balance = balance.balance

            current_db_positions_dict = self.fetch_current_db_positions(session)
            previous_trades = session.query(Trade).filter_by(
                broker=self.broker.broker_name,
                strategy=self.strategy_name,
                order_type='buy'
            ).all()

        if not is_market_open():
            logger.info("Market is closed. Skipping rebalance.")
            return

        await self.handle_previous_positions(current_db_positions_dict, previous_trades)

        valid_put_option = await self.find_valid_option(self.symbol, 'put', total_balance)

        if valid_put_option:
            logger.info(f"Selected OTM put option: {valid_put_option}")

            put_bet_size = total_balance * self.bet_percentage

            await self.place_option_order(valid_put_option['symbol'], put_bet_size // valid_put_option['lastPrice'], 'buy', valid_put_option)

    async def handle_previous_positions(self, current_db_positions_dict, previous_trades):
        with self.broker.Session() as session:
            current_date = datetime.now(UTC).date()
            for position, details in current_db_positions_dict.items():
                trade_date = next((trade.timestamp.date() for trade in previous_trades if trade.symbol == position), None)
                if not trade_date:
                    continue

                days_held = (current_date - trade_date).days
                current_price = await self.broker.get_current_price(position)
                buy_price = next((trade.price for trade in previous_trades if trade.symbol == position), None)
                if not buy_price:
                    continue

                if days_held >= self.holding_period_days or (current_price / buy_price - 1) * 100 >= self.spike_percentage:
                    await self.broker.close_position(position, details['quantity'], self.strategy_name)
                    logger.info(f"Closed position for {position} held for {days_held} days")

    async def find_valid_option(self, symbol, option_type, total_balance):
        current_date = datetime.now(UTC)
        target_exp_date = current_date + timedelta(days=self.expiry_days)
        ticker = yf.Ticker(symbol)
        # Fetch the available expiration dates
        exp_dates = ticker.options
        exp_dates = pd.to_datetime(exp_dates)
        # Find the closest expiration date
        closest_exp_date = min(exp_dates, key=lambda x: abs(x - target_exp_date)).strftime('%Y-%m-%d')
        option = await self.get_otm_option(symbol, closest_exp_date, option_type)
        if option and self.is_order_valid(option, total_balance * self.bet_percentage):
            return option
        else:
            logger.info(f"Invalid {option_type} option for {symbol}, no valid option found.")
            return None

    async def get_otm_option(self, symbol, exp_date, option_type):
        options_chain = await yf.Ticker(symbol).option_chain(exp_date)
        current_price = await self.broker.get_current_price(symbol) if asyncio.iscoroutinefunction(self.broker.get_current_price) else self.broker.get_current_price(symbol)

        if option_type == 'put':
            options = options_chain.puts

        otm_options = options[options['strike'] < current_price * (1 - self.otm_percentage)]
        if len(otm_options) == 0:
            logger.error(f"No OTM {option_type} options found for {symbol}")
            return None

        return otm_options.iloc[0].to_dict()

    def is_order_valid(self, option, bet_size):
        bid = option['bid']
        ask = option['ask']
        last_price = option['lastPrice']
        spread = ask - bid

        if spread / last_price > self.max_spread_percentage:
            logger.error(f"Order for {option['symbol']} rejected due to high spread: {spread / last_price:.2%}")
            return False

        if last_price > bet_size:
            logger.error(f"Order for {option['symbol']} rejected due to high price: {last_price} > {bet_size}")
            return False

        return True

    async def place_option_order(self, symbol, quantity, order_type, option):
        price = option['lastPrice']
        if self.paper_trade:
            logger.info(f"Paper trading: Placed {order_type} order for {symbol}: {quantity} shares at {price}", extra={'strategy_name': self.strategy_name})
            self.broker.place_option_order(symbol, quantity, order_type, self.strategy_name, price, paper_trade=True)
            return
        await self.broker.place_option_order(symbol, quantity, order_type, self.strategy_name, price)
