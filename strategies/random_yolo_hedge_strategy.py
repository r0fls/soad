import random
from datetime import timedelta, datetime, UTC
from database.models import Balance, Trade
from utils.utils import is_market_open
from utils.logger import logger
from strategies.base_strategy import BaseStrategy
import asyncio

class RandomYoloHedge(BaseStrategy):
    # Randomly selects a stock from the NASDAQ 100 index and buys an ATM call and put option
    def __init__(self, broker, strategy_name, rebalance_interval_minutes, starting_capital, max_spread_percentage=0.25, bet_percentage=0.2):
        self.rebalance_interval_minutes = rebalance_interval_minutes
        self.rebalance_interval = timedelta(minutes=rebalance_interval_minutes)
        self.max_spread_percentage = max_spread_percentage
        self.bet_percentage = bet_percentage
        super().__init__(broker, strategy_name, starting_capital)
        logger.info(
            f"Initialized {self.strategy_name} strategy with starting capital {self.starting_capital}")

    async def initialize(self):
        # Initialization if needed
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
                    side='buy'
                ).all()
                quantity = current_db_positions_dict[position]['quantity']
                bid_ask = self.broker.get_bid_ask(position)
                if (bid_ask['ask'] - bid_ask['bid']) / bid_ask['ask'] > self.max_spread_percentage:
                    logger.error(f"Spread too high for {position}, skipping close.")
                    continue
                await self.broker.place_option_order(position, quantity, 'sell', bid_ask['bid'])
                logger.info(f"Closed position for {position}")

        valid_call_option = await self.find_valid_option(index, 'call', total_balance)
        valid_put_option = await self.find_valid_option(index, 'put', total_balance)

        if valid_call_option and valid_put_option:
            logger.info(f"Selected ATM call option: {valid_call_option}")
            logger.info(f"Selected ATM put option: {valid_put_option}")

            # 50/50 split between call and put
            call_bet_size = total_balance * self.bet_percentage * 0.5
            put_bet_size = total_balance * self.bet_percentage * 0.5

            await self.place_option_order(valid_call_option['symbol'], call_bet_size // valid_call_option['lastPrice'], 'buy', valid_call_option)
            await self.place_option_order(valid_put_option['symbol'], put_bet_size // valid_put_option['lastPrice'], 'buy', valid_put_option)

    def get_index_stocks(self):
        # NASDAQ 100 index
        nasdaq_100_tickers = [
            "AAPL", "MSFT", "AMZN", "TSLA", "GOOGL", "GOOG", "META", "NVDA", "PYPL", "ADBE",
            "NFLX", "CMCSA", "PEP", "INTC", "CSCO", "AVGO", "TXN", "QCOM", "AMGN", "CHTR",
            "AMD", "SBUX", "MDLZ", "ISRG", "INTU", "AMAT", "BKNG", "MU", "ADP", "ZM",
            "GILD", "VRTX", "ILMN", "REGN", "JD", "LRCX", "MRVL", "FISV", "CSX", "ATVI",
            "BIIB", "ADSK", "ADI", "ROST", "CTSH", "EA", "MNST", "KDP", "XEL", "SPLK",
            "EBAY", "EXC", "DLTR", "MELI", "SGEN", "FAST", "WDAY", "VRSK", "KLAC", "PAYX",
            "CDNS", "ALXN", "IDXX", "SNPS", "PCAR", "CTAS", "MXIM", "CERN", "CHKP", "SWKS",
            "ANSS", "XLNX", "INCY", "MCHP", "CDW", "SIRI", "NTES", "LULU", "TTWO", "TCOM",
            "CPRT", "BMRN", "PTON", "TEAM", "DLTR", "VRSN", "NTAP", "OKTA", "WDC", "MAR",
            "EXPE", "ULTA", "ORLY", "CTXS", "CSGP", "CDNS", "DXCM", "ASML", "JD", "KLAC"
        ]
        return nasdaq_100_tickers

    async def find_valid_option(self, stocks, option_type, total_balance):
        current_date = datetime.now(UTC)
        exp_date = (current_date + timedelta(days=(4 - current_date.weekday()))).strftime('%Y-%m-%d')
        while stocks:
            stock = random.choice(stocks)
            stocks.remove(stock)
            option = await self.get_atm_option(stock, exp_date, option_type)
            if option and self.is_order_valid(option, total_balance * self.bet_percentage * 0.5):
                return option
            else:
                logger.info(f"Invalid {option_type} option for {stock}, trying another stock.")

        logger.error(f"No valid {option_type} options found.")
        return None

    async def get_atm_option(self, stock, exp_date, option_type):
        options_chain = await self.broker.get_options_chain(stock, exp_date)
        current_price = await self.broker.get_current_price(stock)

        if option_type == 'call':
            options = options_chain['calls']
        else:
            options = options_chain['puts']

        atm_options = [opt for opt in options if abs(opt['strike'] - current_price) < 1]
        if len(atm_options) == 0:
            logger.error(f"No ATM {option_type} options found for {stock}")
            return None

        return atm_options[0]

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

    async def place_option_order(self, symbol, quantity, side, option):
        price = option['lastPrice']
        if self.paper_trade:
            logger.info(f"Paper trading: Placed {side} order for {symbol}: {quantity} shares at {price}", extra={'strategy_name': self.strategy_name})
            self.broker.place_option_order(symbol, quantity, side, self.strategy_name, price, paper_trade=True)
            return
        await self.broker.place_option_order(symbol, quantity, side, self.strategy_name, price)
