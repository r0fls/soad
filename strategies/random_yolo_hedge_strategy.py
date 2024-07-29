import random
from datetime import timedelta, datetime
from database.models import Balance, Trade
from utils.utils import is_market_open
from utils.logger import logger
from strategies.base_strategy import BaseStrategy
import asyncio
import yfinance as yf

class RandomYoloHedge(BaseStrategy):
    def __init__(self, broker, strategy_name, rebalance_interval_minutes, starting_capital, max_spread_percentage=0.25, bet_percentage=0.2, index='NDX'):
        self.index = index
        self.rebalance_interval_minutes = rebalance_interval_minutes
        self.rebalance_interval = timedelta(minutes=rebalance_interval_minutes)
        self.max_spread_percentage = max_spread_percentage
        self.bet_percentage = bet_percentage
        super().__init__(broker, strategy_name, starting_capital)
        logger.info(
            f"Initialized {self.strategy_name} strategy with starting capital {self.starting_capital}")

    async def initialize(self):
        # TODO: why is this needed?
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

        if not is_market_open():
            logger.info("Market is closed. Skipping rebalance.")
            return

        index = self.get_index_stocks()
        if not index:
            logger.error("Failed to fetch index stocks.")
            return

        # Sell previous positions
        with self.broker.Session() as session:
            positions = current_db_positions_dict.keys()
            logger.info(f"Closing previous positions: {positions}")
            for position in positions:
                # Ensure we haven't bought this yet today
                trades = session.query(Trade).filter_by(
                    broker=self.broker.broker_name,
                    symbol=position,
                    timestamp=datetime.now().date(),
                    order_type='buy'
                ).all()
                await self.broker.close_position(position, current_db_positions_dict[position]['quantity'], self.strategy_name)
                logger.info(f"Closed position for {position}")

        valid_call_option = await self.find_valid_option(index, 'call', total_balance)
        valid_put_option = await self.find_valid_option(index, 'put', total_balance)

        if valid_call_option and valid_put_option:
            logger.info(f"Selected ATM call option: {valid_call_option}")
            logger.info(f"Selected ATM put option: {valid_put_option}")

            call_bet_size = total_balance * self.bet_percentage * 0.1
            put_bet_size = total_balance * self.bet_percentage * 0.1

            await self.place_option_order(valid_call_option['symbol'], call_bet_size // valid_call_option['lastPrice'], 'buy', valid_call_option)
            await self.place_option_order(valid_put_option['symbol'], put_bet_size // valid_put_option['lastPrice'], 'buy', valid_put_option)

    def get_index_stocks(self):
        try:
            index_ticker = yf.Ticker(f"^{self.index}")
            index_components = index_ticker.history(period="1d")
            return index_components.index.tolist()
        except Exception as e:
            logger.error(f"Error fetching {self.index} components: {e}")
            return []

    async def find_valid_option(self, stocks, option_type, total_balance):
        current_date = datetime.utcnow()
        exp_date = (current_date + timedelta(days=(4 - current_date.weekday()))).strftime('%Y-%m-%d')
        while stocks:
            stock = random.choice(stocks)
            stocks.remove(stock)
            option = await self.get_atm_option(stock, exp_date, option_type)
            if option and self.is_order_valid(option, total_balance * self.bet_percentage * 0.1):
                return option
            else:
                logger.info(f"Invalid {option_type} option for {stock}, trying another stock.")

        logger.error(f"No valid {option_type} options found.")
        return None

    async def get_atm_option(self, stock, exp_date, option_type):
        options_chain = await yf.Ticker(stock).option_chain(exp_date)
        current_price = await self.broker.get_current_price(stock) if asyncio.iscoroutinefunction(self.broker.get_current_price) else self.broker.get_current_price(stock)

        if option_type == 'call':
            options = options_chain.calls
        else:
            options = options_chain.puts

        atm_options = options[abs(options['strike'] - current_price) < 1]
        if len(atm_options) == 0:
            logger.error(f"No ATM {option_type} options found for {stock}")
            return None

        return atm_options.iloc[0].to_dict()

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
