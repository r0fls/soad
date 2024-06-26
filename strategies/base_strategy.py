from abc import ABC, abstractmethod
from database.models import Balance, Position
from utils.logger import logger
from utils.utils import is_market_open
from datetime import datetime
import asyncio

class BaseStrategy(ABC):
    def __init__(self, broker, strategy_name, starting_capital, rebalance_interval_minutes=5):
        self.broker = broker
        self.strategy_name = strategy_name
        self.starting_capital = starting_capital
        self.initialize_starting_balance()
        self.rebalance_interval_minutes = rebalance_interval_minutes

    @abstractmethod
    async def rebalance(self):
        pass

    def initialize_starting_balance(self):
        logger.debug("Initializing starting balance")

        account_info = self.broker.get_account_info()
        buying_power = account_info.get('buying_power')
        logger.debug(f"Account info: {account_info}")

        if buying_power < self.starting_capital:
            logger.error(f"Not enough cash available. Required: {self.starting_capital}, Available: {buying_power}")
            raise ValueError("Not enough cash available to initialize the strategy with the desired starting capital.")

        with self.broker.Session() as session:
            strategy_balance = session.query(Balance).filter_by(
                strategy=self.strategy_name,
                broker=self.broker.broker_name,
                type='cash'
            ).first()

            if strategy_balance is None:
                strategy_balance = Balance(
                    strategy=self.strategy_name,
                    broker=self.broker.broker_name,
                    type='cash',
                    balance=self.starting_capital
                )
                session.add(strategy_balance)
                session.commit()
                logger.info(f"Initialized starting balance for {self.strategy_name} strategy with {self.starting_capital}")
            else:
                logger.info(f"Existing balance found for {self.strategy_name} strategy: {strategy_balance.balance}")

    async def sync_positions_with_broker(self):
        logger.debug("Syncing positions with broker")

        broker_positions = self.broker.get_positions()
        logger.debug(f"Broker positions: {broker_positions}")

        with self.broker.Session() as session:
            for symbol, data in broker_positions.items():
                if asyncio.iscoroutinefunction(self.broker.get_current_price):
                    current_price = await self.broker.get_current_price(symbol)
                else:
                    current_price = self.broker.get_current_price(symbol)
                target_quantity = self.should_own(symbol, current_price)
                if target_quantity > 0:
                    position = session.query(Position).filter_by(
                        broker=self.broker.broker_name,
                        strategy=None,
                        symbol=symbol
                    ).first()
                    if not position:
                        position = session.query(Position).filter_by(
                            broker=self.broker.broker_name,
                            strategy=self.strategy_name,
                            symbol=symbol
                        ).first()
                    if position:
                        position.strategy = self.strategy_name
                        position.quantity = data['quantity']
                        position.latest_price = current_price
                        position.last_updated = datetime.utcnow()
                        logger.info(
                            f"Updated uncategorized position for {symbol} to strategy {self.strategy_name} with quantity {data['quantity']} and price {current_price}")
                    else:
                        position = Position(
                            broker=self.broker.broker_name,
                            strategy=self.strategy_name,
                            symbol=symbol,
                            quantity=data['quantity'],
                            latest_price=current_price,
                            last_updated=datetime.utcnow()
                        )
                        session.add(position)
                        logger.info(
                            f"Created new position for {symbol} with quantity {data['quantity']} and price {current_price}")

            db_positions = session.query(Position).filter_by(
                broker=self.broker.broker_name,
                strategy=self.strategy_name
            ).all()

            broker_symbols = set(broker_positions.keys())

            for position in db_positions:
                if position.symbol not in broker_symbols:
                    logger.info(f"Removing position for {position.symbol} as it's not in broker's positions")
                    session.delete(position)

            session.commit()
            logger.debug("Positions synced with broker")

    def should_own(self, symbol, current_price):
        pass

    def get_current_positions(self):
        positions = self.broker.get_positions()
        positions_dict = {
            position: positions[position]['quantity'] for position in positions}
        logger.debug(f"Retrieved current positions: {positions_dict}")
        return positions_dict

    def get_account_info(self):
        account_info = self.broker.get_account_info()
        if not account_info:
            logger.error("Failed to fetch account information")
            raise ValueError("Failed to fetch account information")
        logger.debug(f"Account info: {account_info}")
        return account_info

    def calculate_target_balances(self, total_balance, cash_percentage):
        target_cash_balance = total_balance * cash_percentage
        target_investment_balance = total_balance - target_cash_balance
        logger.debug(
            f"Target cash balance: {target_cash_balance}, Target investment balance: {target_investment_balance}")
        return target_cash_balance, target_investment_balance

    def fetch_current_db_positions(self, session):
        current_db_positions = session.query(Position).filter_by(
            strategy=self.strategy_name,
            broker=self.broker.broker_name
        ).all()
        current_db_positions_dict = {
            pos.symbol: pos.quantity for pos in current_db_positions if pos.quantity > 0}
        logger.debug(f"Current DB positions: {current_db_positions_dict}")
        return current_db_positions_dict

    async def place_opttion_order(self, symbol, quantity, order_type, price, wait_till_open=True):
        if is_market_open() or not wait_till_open:
            if asyncio.iscoroutinefunction(self.broker.place_option_order):
                await self.broker.place_order(stock, quantity, order_type, self.strategy_name, price)
            else:
                self.broker.place_option_order(stock, quantity, order_type, self.strategy_name, price)
            logger.info(
                f"Placed {order_type} order for {symbol}: {quantity} shares")
        else:
            logger.info(
                f"Market is closed, not placing {order_type} order for {symbol}: {quantity} shares")

    async def place_order(self, stock, quantity, order_type, price, wait_till_open=True):
        if is_market_open() or not wait_till_open:
            if asyncio.iscoroutinefunction(self.broker.place_order):
                await self.broker.place_order(stock, quantity, order_type, self.strategy_name, price)
            else:
                self.broker.place_order(stock, quantity, order_type, self.strategy_name, price)
            logger.info(
                f"Placed {order_type} order for {stock}: {quantity} shares")
        else:
            logger.info(
                f"Market is closed, not placing {order_type} order for {stock}: {quantity} shares")
